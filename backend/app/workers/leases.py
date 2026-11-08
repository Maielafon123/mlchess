"""Queue-scoped SQL leases. Inference and game locks stay outside claim/failure."""

from dataclasses import dataclass
from datetime import timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import and_, or_, select, update

from backend.app.games.durable import DurableGameService
from backend.app.infra.models import WorkerJob


@dataclass(frozen=True)
class Lease:
    id: UUID
    token: UUID
    game_id: UUID
    version: int
    revision: int


class LeasedWorker:
    queue: str

    def __init__(self, factory, *, lease_seconds=30, max_attempts=3):
        if not 30 <= lease_seconds <= 300 or not 1 <= max_attempts <= 10:
            raise ValueError("Invalid worker bounds")
        if self.queue not in {"gameplay", "analysis", "coach"}:
            raise ValueError("Unknown worker queue")
        self.factory = factory
        self.lease_seconds, self.max_attempts = lease_seconds, max_attempts

    async def claim(self) -> Lease | None:
        async with self.factory() as session, session.begin():
            now = await DurableGameService.now(session)
            await session.execute(
                update(WorkerJob)
                .where(
                    WorkerJob.queue == self.queue,
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
                    WorkerJob.queue == self.queue,
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

    async def fail(self, lease, code: str, *, stale: bool = False) -> str:
        async with self.factory() as session, session.begin():
            job = await session.scalar(
                select(WorkerJob)
                .where(WorkerJob.id == lease.id, WorkerJob.queue == self.queue)
                .with_for_update()
            )
            if job is None or job.status != "running" or job.lease_token != lease.token:
                return "lost"
            now = await DurableGameService.now(session)
            deadline = job.lease_until
            if (
                deadline if deadline.tzinfo else deadline.replace(tzinfo=timezone.utc)
            ) <= now:
                return "lost"
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
