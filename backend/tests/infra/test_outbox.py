from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from sqlalchemy import select

from backend.app.infra.db import create_engine, create_schema, session_factory
from backend.app.infra.models import OutboxEvent
from backend.app.infra.outbox import OutboxDispatcher


class Publisher:
    def __init__(self, fail=False):
        self.events = []
        self.fail = fail

    async def publish(self, **event):
        if self.fail:
            raise RuntimeError("broker unavailable")
        self.events.append(event)


def test_dispatcher_rejects_unbounded_batches_without_opening_db():
    with pytest.raises(ValueError):
        OutboxDispatcher.validate_batch_limit(0)


def test_event_ids_are_uuid_values_for_publishers():
    event_id = uuid4()
    assert event_id.version == 4


def test_failed_dispatch_keeps_durable_event_and_retries_its_same_id(tmp_path):
    async def scenario():
        engine = create_engine(
            "sqlite+aiosqlite:///" + (tmp_path / "outbox.db").as_posix()
        )
        await create_schema(engine)
        factory = session_factory(engine)
        event_id, game_id = uuid4(), uuid4()
        publisher = Publisher(fail=True)
        dispatcher = OutboxDispatcher(factory, publisher)
        try:
            async with factory() as session, session.begin():
                session.add(
                    OutboxEvent(
                        id=event_id,
                        aggregate_type="game",
                        aggregate_id=game_id,
                        event_type="game.move_committed",
                        payload={"private": "fixture"},
                    )
                )
            assert await dispatcher.dispatch_batch() == 0
            async with factory() as session:
                row = await session.scalar(select(OutboxEvent))
                assert row.published_at is None and row.attempts == 1
            publisher.fail = False
            assert await dispatcher.dispatch_batch() == 1
            assert await dispatcher.dispatch_batch() == 0
            assert publisher.events == [
                {
                    "event_id": event_id,
                    "event_type": "game.move_committed",
                    "aggregate_type": "game",
                    "aggregate_id": game_id,
                }
            ]
            async with factory() as session:
                row = await session.get(OutboxEvent, event_id)
                assert row.published_at is not None and row.attempts == 2
                assert row.payload == {"private": "fixture"}
        finally:
            await engine.dispose()

    asyncio.run(scenario())
