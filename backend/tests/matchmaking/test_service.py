from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from backend.app.matchmaking.service import (
    InMemoryMatchmaker,
    MatchmakingError,
    TicketStatus,
)


def test_matching_is_deduplicated_and_same_pool_only():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    service = InMemoryMatchmaker()
    first = service.create(
        user_id=uuid4(), time_control="10+0", rating_pool="main", now=now
    )
    second = service.create(
        user_id=uuid4(), time_control="10+0", rating_pool="main", now=now
    )
    result = service.match(now=now)
    assert result is not None
    left, right, game_id = result
    assert {left.id, right.id} == {first.id, second.id}
    assert game_id == left.game_id == right.game_id
    assert left.status is TicketStatus.MATCHED
    assert service.match(now=now) is None


def test_duplicate_user_cancel_and_expiry_are_safe():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    service = InMemoryMatchmaker(ttl_seconds=10)
    user = uuid4()
    ticket = service.create(
        user_id=user, time_control="3+2", rating_pool="main", now=now
    )
    with pytest.raises(MatchmakingError):
        service.create(user_id=user, time_control="3+2", rating_pool="main", now=now)
    service.cancel(ticket.id, user_id=user)
    expired = service.create(
        user_id=uuid4(), time_control="3+2", rating_pool="main", now=now
    )
    service.expire(now=now + timedelta(seconds=11))
    assert expired.status is TicketStatus.EXPIRED
