"""Independent SQL coach worker over B's grounded provider/service boundary."""

import argparse
import asyncio
from datetime import timezone
import json

from sqlalchemy import select

from backend.app.coach.analysis_reader import grounded_request, read_verified
from backend.app.coach.durable import domain_request
from backend.app.coach.execution import execute
from backend.app.coach.providers.rules import RulesCoachProvider
from backend.app.coach.service import CoachJob
from backend.app.games.durable import DurableGameService
from backend.app.infra.db import create_engine, session_factory
from backend.app.infra.models import CoachExplanation, Game, User, WorkerJob
from backend.app.infra.problems import PublicProblem
from backend.app.infra.settings import Settings
from backend.app.workers.leases import LeasedWorker


class CoachWorker(LeasedWorker):
    queue = "coach"

    @staticmethod
    async def current(session, lease):
        row = await session.get(CoachExplanation, lease.id)
        if (
            row is None
            or row.game_id != lease.game_id
            or row.revision != lease.revision
        ):
            return None
        user = await session.get(User, row.requester_id)
        now = await DurableGameService.now(session)
        if user is None or user.deleted_at is not None:
            return None
        expiry = user.expires_at
        if (
            expiry
            and (expiry if expiry.tzinfo else expiry.replace(tzinfo=timezone.utc))
            <= now
        ):
            return None
        request = domain_request(row)
        try:
            game, state, analysis = await read_verified(
                session, row.requester_id, request, lock=False
            )
        except PublicProblem:
            return None
        request, facts = grounded_request(request, analysis)
        return row, game, state, request, facts

    async def position(self, lease):
        async with self.factory() as session:
            current = await self.current(session, lease)
            if current is None:
                return None
            return current[3], current[4]

    async def apply(self, lease, explanation, failure_code):
        async with self.factory() as session, session.begin():
            await session.scalar(
                select(Game).where(Game.id == lease.game_id).with_for_update()
            )
            job = await session.scalar(
                select(WorkerJob)
                .where(WorkerJob.id == lease.id, WorkerJob.queue == self.queue)
                .with_for_update()
            )
            now = await DurableGameService.now(session)
            if job is None or job.status != "running" or job.lease_token != lease.token:
                return "lost"
            deadline = job.lease_until
            if (
                deadline if deadline.tzinfo else deadline.replace(tzinfo=timezone.utc)
            ) <= now:
                return "lost"
            current = await self.current(session, lease)
            if current is None:
                job.status, job.failure_code = "stale", "STALE_REVISION"
            else:
                from backend.app.coach.grounding import validate_explanation

                row, game, state, request, facts = current
                checked = validate_explanation(explanation, request, facts)
                row.payload_json, row.status = checked.explanation, "ready"
                row.fallback_used = checked.explanation["fallback_used"]
                row.error_code = (
                    "PROVIDER_UNAVAILABLE"
                    if failure_code or checked.failure_code
                    else None
                )
                job.status, job.output = "done", {"coach_job_id": str(row.id)}
                DurableGameService.event(
                    session,
                    game,
                    state,
                    "coach.ready",
                    {
                        "explanation_id": str(row.id),
                        "analysis_id": str(row.analysis_id),
                        "revision": row.revision,
                        "ply": row.ply,
                    },
                    now,
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
                return await self.fail(lease, "STALE_REVISION", stale=True)
            request, facts = position
            explanation, code = await asyncio.to_thread(
                execute,
                RulesCoachProvider(),
                CoachJob(id=str(lease.id), request=request, cache_key="durable"),
                facts,
            )
            return await self.apply(lease, explanation, code)
        except Exception:
            return await self.fail(lease, "COACH_FAILURE")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    settings = Settings()
    if not settings.database_url or not settings.database_url.startswith(
        "postgresql+asyncpg://"
    ):
        parser.error("Coach worker requires migrated PostgreSQL")

    async def run():
        engine = create_engine(settings.database_url)
        worker = CoachWorker(session_factory(engine))
        try:
            while True:
                status = await worker.run_one()
                if status:
                    print(
                        json.dumps({"event": "coach.job", "status": status}), flush=True
                    )
                if args.once:
                    return 1 if status == "failed" else 0
                if status is None:
                    await asyncio.sleep(0.5)
        finally:
            await engine.dispose()

    return asyncio.run(run())


if __name__ == "__main__":
    raise SystemExit(main())
