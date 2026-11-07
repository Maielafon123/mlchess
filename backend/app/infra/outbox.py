from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .models import OutboxEvent


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class QueuePublisher(Protocol):
    async def publish(
        self, *, event_id: UUID, event_type: str, payload: dict
    ) -> None: ...


class OutboxDispatcher:
    """Publishes committed outbox rows; broker acknowledgement is not DB success."""

    def __init__(
        self, factory: async_sessionmaker[AsyncSession], publisher: QueuePublisher
    ):
        self.factory = factory
        self.publisher = publisher

    @staticmethod
    def validate_batch_limit(limit: int) -> None:
        if not 1 <= limit <= 500:
            raise ValueError("limit must be between 1 and 500")

    async def dispatch_batch(self, *, limit: int = 50) -> int:
        self.validate_batch_limit(limit)
        async with self.factory() as session:
            result = await session.execute(
                select(OutboxEvent)
                .where(OutboxEvent.published_at.is_(None))
                .order_by(OutboxEvent.created_at, OutboxEvent.id)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
            events = list(result.scalars())
            count = 0
            for event in events:
                event.attempts += 1
                try:
                    await self.publisher.publish(
                        event_id=event.id,
                        event_type=event.event_type,
                        payload=event.payload,
                    )
                except Exception:
                    continue
                event.published_at = utcnow()
                count += 1
            await session.commit()
            return count


async def repair_stuck_jobs(
    session: AsyncSession, *, older_than: datetime, max_attempts: int
) -> int:
    """Return queued outbox rows to a retryable state without deleting evidence."""
    result = await session.execute(
        update(OutboxEvent)
        .where(
            OutboxEvent.published_at.is_(None),
            OutboxEvent.created_at < older_than,
            OutboxEvent.attempts >= max_attempts,
        )
        .values(attempts=0)
    )
    await session.commit()
    return result.rowcount or 0
