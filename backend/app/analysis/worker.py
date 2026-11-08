"""Independent bounded analysis worker; SQL leases fence late/stale publication."""

import argparse
import asyncio
from datetime import timezone
import json
import os
from pathlib import Path
from uuid import UUID

from sqlalchemy import select

from backend.app.analysis.durable import POLICY, POLICY_BINARY_SHA256, require_analysis
from backend.app.analysis.evaluate import evaluate
from backend.app.analysis.service import reconstruct_position
from backend.app.engine.adapter import EngineError, UciEngineAdapter
from backend.app.engine.manifest import load_manifest
from backend.app.games.domain import GameDomain
from backend.app.games.durable import DurableGameService, decode_domain, iso
from backend.app.infra.db import create_engine, session_factory
from backend.app.infra.models import (
    Analysis,
    Game,
    GameState,
    OutboxEvent,
    User,
    WorkerJob,
)
from backend.app.infra.problems import PublicProblem
from backend.app.infra.settings import Settings
from backend.app.workers.leases import LeasedWorker


class AnalysisWorker(LeasedWorker):
    queue = "analysis"

    def __init__(self, factory, engine, metadata, **kwargs):
        super().__init__(factory, **kwargs)
        self.engine, self.metadata = engine, metadata

    @staticmethod
    async def current(session, lease):
        row = await session.get(Analysis, lease.id)
        event = await session.get(OutboxEvent, lease.id)
        if (
            row is None
            or row.game_id != lease.game_id
            or event is None
            or event.payload.get("policy") != POLICY
        ):
            return None
        actor_id = UUID(event.payload["actor_id"])
        actor = await session.get(User, actor_id)
        now = await DurableGameService.now(session)
        if actor is None or actor.deleted_at is not None:
            return None
        expiry = actor.expires_at
        if (
            expiry
            and (expiry if expiry.tzinfo else expiry.replace(tzinfo=timezone.utc))
            <= now
        ):
            return None
        try:
            game, state, _ = await DurableGameService.load(
                session, lease.game_id, actor_id, lock=True
            )
            require_analysis(game)
            if row.revision != game.revision or row.revision != lease.revision:
                return None
            slice_ = reconstruct_position(decode_domain(state.domain), row.ply)
            if slice_.position_key != event.payload["position_key"]:
                return None
        except (PublicProblem, ValueError):
            return None
        return row, event, slice_

    async def position(self, lease):
        async with self.factory() as session:
            current = await self.current(session, lease)
            if current is None:
                return None
            row, event, slice_ = current
            captured = GameDomain.from_history(
                "coach",
                event.payload["moves"],
                initial_fen=event.payload["initial_fen"],
            )
            stored = reconstruct_position(captured, row.ply)
            if (
                stored.position_key != slice_.position_key
                or stored.after.fen() != slice_.after.fen()
            ):
                return None
            return stored, event.payload["level"]

    async def apply(self, lease, result):
        async with self.factory() as session, session.begin():
            # Same game -> job lock order as gameplay; claims never acquire games.
            await session.scalar(
                select(Game).where(Game.id == lease.game_id).with_for_update()
            )
            job = await session.scalar(
                select(WorkerJob)
                .where(WorkerJob.id == lease.id, WorkerJob.queue == self.queue)
                .with_for_update()
            )
            now = await DurableGameService.now(session)
            deadline = job.lease_until if job else None
            if (
                job is None
                or job.status != "running"
                or job.lease_token != lease.token
                or (
                    deadline
                    if deadline.tzinfo
                    else deadline.replace(tzinfo=timezone.utc)
                )
                <= now
            ):
                return "lost"
            current = await self.current(session, lease)
            if current is None:
                job.status, job.failure_code = "stale", "STALE_POSITION"
            else:
                row, _, slice_ = current
                if (
                    result["analysis_id"],
                    result["game_id"],
                    result["revision"],
                    result["position_key"],
                    result["before_fen"],
                    result["after_fen"],
                ) != (
                    str(row.id),
                    str(lease.game_id),
                    lease.revision,
                    slice_.position_key,
                    slice_.before.fen(),
                    slice_.after.fen(),
                ):
                    raise EngineError("Analysis result identity mismatch")
                row.result, row.status, row.updated_at = result, "done", now
                game = await session.get(Game, lease.game_id)
                state = await session.get(GameState, lease.game_id)
                DurableGameService.event(
                    session,
                    game,
                    state,
                    "analysis.ready",
                    {
                        "analysis_id": str(row.id),
                        "revision": row.revision,
                        "ply": row.ply,
                    },
                    now,
                )
                job.status, job.failure_code, job.output = (
                    "done",
                    None,
                    {"analysis_id": str(row.id)},
                )
            job.finished_at, job.lease_token, job.lease_until = now, None, None
            return job.status

    async def run_one(self):
        lease = await self.claim()
        if lease is None:
            return None
        try:
            position = await self.position(lease)
            if position is None:
                return await self.fail(lease, "STALE_POSITION", stale=True)
            slice_, level = position
            async with self.factory() as session:
                now = await DurableGameService.now(session)
            result = await asyncio.to_thread(
                evaluate,
                self.engine,
                slice_,
                analysis_id=lease.id,
                game_id=lease.game_id,
                revision=lease.revision,
                level=level,
                metadata=self.metadata,
                created_at=iso(now),
            )
            return await self.apply(lease, result)
        except (EngineError, ValueError):
            return await self.fail(lease, "ENGINE_FAILURE")
        except Exception:
            return await self.fail(lease, "WORKER_FAILURE")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    settings = Settings()
    if not settings.database_url or not settings.database_url.startswith(
        "postgresql+asyncpg://"
    ):
        parser.error("Analysis worker requires migrated PostgreSQL")
    binary, digest, manifest = (
        os.environ.get(name)
        for name in (
            "MLCHESS_STOCKFISH_BINARY",
            "MLCHESS_STOCKFISH_SHA256",
            "MLCHESS_STOCKFISH_MANIFEST",
        )
    )
    if not binary or not digest or not manifest:
        parser.error("Pinned engine and build-time NNUE manifest are required")
    adapter = UciEngineAdapter(Path(binary), sha256=digest)
    try:
        metadata = load_manifest(Path(manifest), adapter)
        if metadata["binary_sha256"] != POLICY_BINARY_SHA256:
            raise EngineError("Analysis policy does not match the pinned engine")

        async def run():
            engine = create_engine(settings.database_url)
            worker = AnalysisWorker(session_factory(engine), adapter, metadata)
            try:
                while True:
                    status = await worker.run_one()
                    if status:
                        print(
                            json.dumps({"event": "analysis.job", "status": status}),
                            flush=True,
                        )
                    if args.once:
                        return 1 if status == "failed" else 0
                    if status is None:
                        await asyncio.sleep(0.5)
            finally:
                await engine.dispose()

        return asyncio.run(run())
    finally:
        adapter.stop()


if __name__ == "__main__":
    raise SystemExit(main())
