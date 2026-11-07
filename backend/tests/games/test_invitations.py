from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from backend.app.games.invitations import InMemoryInvitationService, InvitationError


def test_invitation_stores_hash_and_is_single_use():
    service = InMemoryInvitationService()
    creator, guest = uuid4(), uuid4()
    invitation, token = service.create(
        game_id=uuid4(),
        creator_id=creator,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    assert invitation.token_hash != token
    accepted = service.accept(token, actor_id=guest)
    assert accepted.accepted_by == guest
    with pytest.raises(InvitationError):
        service.accept(token, actor_id=uuid4())


def test_invitation_rejects_expired_and_self_acceptance():
    service = InMemoryInvitationService()
    creator = uuid4()
    invitation, token = service.create(
        game_id=uuid4(),
        creator_id=creator,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    with pytest.raises(InvitationError):
        service.accept(token, actor_id=creator)
    with pytest.raises(InvitationError):
        service.accept(
            token,
            actor_id=uuid4(),
            now=invitation.expires_at + timedelta(seconds=1),
        )
