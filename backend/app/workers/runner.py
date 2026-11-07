"""Separate bounded gameplay worker with durable PostgreSQL leases and fencing."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
from dataclasses import asdict, dataclass
from datetime import timedelta
from pathlib import Path
from typing import Protocol
from uuid import UUID, uuid4

import chess
from sqlalchemy import and_, or_, select, update

from backend.app.engine.adapter import (
    EngineBudget,
    EngineError,
    EngineMove,
    UciEngineAdapter,
)
from backend.app.games.clocks import ServerClock
from backend.app.games.durable import (
    DurableGameService,
    decode_clock,
    decode_domain,
    public_clock,
)
from backend.app.infra.db import create_engine, session_factory
from backend.app.infra.models import Game, GameMove, GamePlayer, GameState, WorkerJob
from backend.app.infra.settings import Settings


class MoveEngine(Protocol):
    def choose_move(
        self, board: chess.Board, *, budget: EngineBudget, profile: str
    ) -> EngineMove: ...


@dataclass(frozen=True)
class Lease:
    id: UUID
    token: UUID
    game_id: UUID
    version: int
    revision: int


BUDGETS = {
    "beginner": EngineBudget(time_ms=100, depth=4),
    "casual": EngineBudget(time_ms=200, depth=8),
    "club": EngineBudget(time_ms=300, depth=12),
    "strong": EngineBudget(time_ms=500, depth=16),
}


class GameplayWorker:
    def __init__(
        self,
        factory,
        engine: MoveEngine,
        *,
        lease_seconds: int = 30,
        max_attempts: int = 3,
    ):
        if not 30 <= lease_seconds <= 300 or not 1 <= max_attempts <= 10:
            raise ValueError("Invalid worker bounds")
        self.factory, self.engine = factory, engine
        self.lease_seconds, self.max_attempts = lease_seconds, max_attempts

    async def claim(self) -> Lease | None:
        async with self.factory() as session, session.begin():
            now = await DurableGameService.now(session)
            await session.execute(
                update(WorkerJob)
                .where(
                    WorkerJob.queue == "gameplay",
                    WorkerJob.status == "running",
                    WorkerJob.lease_until <= now,
                    WorkerJob.attempts >= self.max_attempts,
                )
                .values(
                    status="failed",
                    failure_code="LEASE_EXHAUSTED",
                    finished_at=now,
                    lease_token=None,
                    lease_until=None,
                )
            )
            job = await session.scalar(
                select(WorkerJob)
                .where(
                    WorkerJob.queue == "gameplay",
                    WorkerJob.attempts < self.max_attempts,
                    or_(
                        and_(
                            WorkerJob.status == "pending", WorkerJob.available_at <= now
                        ),
                        and_(
                            WorkerJob.status == "running", WorkerJob.lease_until <= now
                        ),
                    ),
                )
                .order_by(WorkerJob.created_at, WorkerJob.id)
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            if job is None:
                return None
            job.status, job.lease_token = "running", uuid4()
            job.attempts += 1
            job.lease_until = now + timedelta(seconds=self.lease_seconds)
            return Lease(
                job.id, job.lease_token, job.game_id, job.expected_version, job.revision
            )

    @staticmethod
    def matches(game, state, players, lease):
        if (
            game is None
            or state is None
            or game.status != "active"
            or game.mode not in {"ai", "coach"}
        ):
            return False
        domain = decode_domain(state.domain)
        engine_players = [p for p in players if p.kind == "engine"]
        return (
            domain.status == "active"
            and domain.mode.value == game.mode
            and domain.version == game.version
            and domain.revision == game.revision
            and domain.fen == game.fen
            and domain.version == lease.version
            and domain.revision == lease.revision
            and len(engine_players) == 1
            and (engine_players[0].side == "white") == domain.side_to_move
        )

    async def position(self, lease):
        async with self.factory() as session:
            game = await session.get(Game, lease.game_id)
            state = await session.get(GameState, lease.game_id)
            players = list(
                await session.scalars(
                    select(GamePlayer).where(GamePlayer.game_id == lease.game_id)
                )
            )
            if not self.matches(game, state, players, lease):
                return None
            return decode_domain(state.domain).board, state.config["ai_profile"]

    async def fail(self, lease, code: str, *, stale: bool = False) -> str:
        async with self.factory() as session, session.begin():
            job = await session.scalar(
                select(WorkerJob).where(WorkerJob.id == lease.id).with_for_update()
            )
            if job is None or job.status != "running" or job.lease_token != lease.token:
                return "lost"
            now = await DurableGameService.now(session)
            job.failure_code = code
            job.lease_token, job.lease_until = None, None
            if stale or job.attempts >= self.max_attempts:
                job.status = "stale" if stale else "failed"
                job.finished_at = now
            else:
                job.status, job.available_at = (
                    "pending",
                    now + timedelta(seconds=min(30, 2**job.attempts)),
                )
            return job.status

    async def apply(self, lease, move: EngineMove) -> str:
        async with self.factory() as session, session.begin():
            # Lock order: game then job. Claim/failure transactions never acquire a game.
            game = await session.scalar(
                select(Game).where(Game.id == lease.game_id).with_for_update()
            )
            job = await session.scalar(
                select(WorkerJob).where(WorkerJob.id == lease.id).with_for_update()
            )
            now = await DurableGameService.now(session)
            if (
                job is None
                or job.status != "running"
                or job.lease_token != lease.token
                or job.lease_until <= now
            ):
                return "lost"
            state = await session.get(GameState, lease.game_id)
            players = list(
                await session.scalars(
                    select(GamePlayer).where(GamePlayer.game_id == lease.game_id)
                )
            )
            if not self.matches(game, state, players, lease):
                job.status, job.failure_code, job.finished_at = (
                    "stale",
                    "STALE_POSITION",
                    now,
                )
                job.lease_token, job.lease_until = None, None
                return "stale"
            domain, clock = decode_domain(state.domain), decode_clock(state.clock)
            if (
                clock
                and clock.running_side is not None
                and clock.remaining(clock.running_side, now=now) == 0
            ):
                domain = domain.timeout(loser=clock.running_side)
                clock = ServerClock(
                    clock.remaining(True, now=now),
                    clock.remaining(False, now=now),
                    clock.increment_ms,
                )
                DurableGameService.save(game, state, domain, clock, now)
                DurableGameService.status_event(session, game, state, clock, now)
                job.status, job.failure_code = "stale", "CLOCK_EXPIRED"
            else:
                updated = domain.play(
                    actor=domain.side_to_move,
                    uci=move.uci,
                    expected_version=lease.version,
                )
                state.config = {
                    **state.config,
                    "clock_history": [*state.config["clock_history"], state.clock],
                }
                if clock:
                    clock = clock.after_legal_move(
                        actor=domain.side_to_move, server_now=now
                    )
                    if updated.result is not None:
                        clock = ServerClock(
                            clock.remaining(True, now=now),
                            clock.remaining(False, now=now),
                            clock.increment_ms,
                        )
                DurableGameService.save(game, state, updated, clock, now)
                record = updated.moves[-1]
                session.add(
                    GameMove(
                        game_id=game.id,
                        actor_id=None,
                        worker_job_id=job.id,
                        client_move_id=job.id,
                        expected_version=lease.version,
                        version=updated.version,
                        ply=updated.ply,
                        revision=updated.revision,
                        uci=record.uci,
                        san=record.san,
                        fen_after=updated.fen,
                        created_at=now,
                    )
                )
                DurableGameService.event(
                    session,
                    game,
                    state,
                    "game.move_committed",
                    {
                        "version": updated.version,
                        "revision": updated.revision,
                        "move": asdict(record),
                        "fen": updated.fen,
                        "side_to_move": "white" if updated.side_to_move else "black",
                        "clock": public_clock(clock, now),
                    },
                    now,
                )
                if updated.result is not None:
                    DurableGameService.status_event(session, game, state, clock, now)
                job.status, job.failure_code = "done", None
                job.output = {
                    "uci": move.uci,
                    "version": updated.version,
                    "revision": updated.revision,
                }
            job.finished_at, job.lease_token, job.lease_until = now, None, None
            return job.status

    async def run_one(self) -> str | None:
        lease = await self.claim()
        if lease is None:
            return None
        try:
            position = await self.position(lease)
            if position is None:
                return await self.fail(lease, "STALE_POSITION", stale=True)
            board, profile = position
            move = await asyncio.to_thread(
                self.engine.choose_move, board, budget=BUDGETS[profile], profile=profile
            )
            if chess.Move.from_uci(move.uci) not in board.legal_moves:
                raise EngineError("Illegal engine move")
            return await self.apply(lease, move)
        except (EngineError, ValueError):
            return await self.fail(lease, "ENGINE_FAILURE")
        except Exception:
            return await self.fail(lease, "WORKER_FAILURE")


class FakeEngine:
    def choose_move(self, board, **kwargs):
        return EngineMove(sorted(move.uci() for move in board.legal_moves)[0])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--fake", action="store_true", help="Development/test only")
    parser.add_argument(
        "--binary", type=Path, default=os.environ.get("MLCHESS_STOCKFISH_BINARY")
    )
    parser.add_argument("--sha256", default=os.environ.get("MLCHESS_STOCKFISH_SHA256"))
    args = parser.parse_args()
    settings = Settings()
    if not settings.database_url or not settings.database_url.startswith(
        "postgresql+asyncpg://"
    ):
        parser.error("Worker requires a migrated PostgreSQL database")
    if args.fake and settings.environment not in {"test", "development"}:
        parser.error("Fake engine is forbidden in deployed environments")
    if not args.fake and (
        not args.binary
        or not args.sha256
        or re.fullmatch(r"[a-fA-F0-9]{64}", args.sha256) is None
    ):
        parser.error("Pinned Stockfish binary and SHA256 are required")
    adapter = (
        FakeEngine() if args.fake else UciEngineAdapter(args.binary, sha256=args.sha256)
    )

    async def run():
        engine = create_engine(settings.database_url)
        worker = GameplayWorker(session_factory(engine), adapter)
        try:
            while True:
                status = await worker.run_one()
                if status:
                    print(
                        json.dumps({"event": "gameplay.job", "status": status}),
                        flush=True,
                    )
                if args.once:
                    return 1 if status == "failed" else 0
                if status is None:
                    await asyncio.sleep(0.5)
        finally:
            await engine.dispose()

    try:
        return asyncio.run(run())
    finally:
        if isinstance(adapter, UciEngineAdapter):
            adapter.stop()


if __name__ == "__main__":
    raise SystemExit(main())
