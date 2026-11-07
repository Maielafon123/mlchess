from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4


class InvitationError(ValueError):
    pass


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()


@dataclass
class Invitation:
    id: UUID
    game_id: UUID
    creator_id: UUID
    token_hash: str
    expires_at: datetime
    accepted_by: UUID | None = None
    accepted_at: datetime | None = None


class InMemoryInvitationService:
    def __init__(self) -> None:
        self._items: dict[UUID, Invitation] = {}

    def create(
        self, *, game_id: UUID, creator_id: UUID, expires_at: datetime
    ) -> tuple[Invitation, str]:
        if expires_at <= datetime.now(timezone.utc):
            raise InvitationError("invitation expiry must be in the future")
        raw = secrets.token_urlsafe(32)
        invitation = Invitation(uuid4(), game_id, creator_id, _hash(raw), expires_at)
        self._items[invitation.id] = invitation
        return invitation, raw

    def accept(
        self, raw_token: str, *, actor_id: UUID, now: datetime | None = None
    ) -> Invitation:
        now = now or datetime.now(timezone.utc)
        for invitation in self._items.values():
            if hmac.compare_digest(invitation.token_hash, _hash(raw_token)):
                if (
                    invitation.accepted_by is not None
                    or invitation.accepted_at is not None
                ):
                    raise InvitationError("invitation has already been accepted")
                if invitation.expires_at <= now:
                    raise InvitationError("invitation has expired")
                if actor_id == invitation.creator_id:
                    raise InvitationError("creator cannot accept own invitation")
                invitation.accepted_by = actor_id
                invitation.accepted_at = now
                return invitation
        raise InvitationError("invitation is invalid")
