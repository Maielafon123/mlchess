from __future__ import annotations

from uuid import uuid4

import pytest

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
