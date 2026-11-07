"""Durable unrated invitations. Raw join tokens never enter DB receipts."""

from __future__ import annotations

import base64
from dataclasses import replace
from datetime import timedelta, timezone
import hashlib
import hmac
from uuid import UUID, uuid4

import chess
from sqlalchemy import func, select

from backend.app.games.clocks import ServerClock
from backend.app.games.durable import (
    DurableGameService,
    decode_clock,
    decode_domain,
    fingerprint,
    iso,
)
from backend.app.infra.models import GamePlayer, Invitation
from backend.app.infra.problems import PublicProblem


class InvitationService:
    def __init__(self, factory, *, secret: str, public_origin: str):
        self.factory, self.secret, self.public_origin = (
            factory,
            secret.encode("ascii"),
            public_origin,
        )

    def token(self, invitation_id: UUID) -> str:
        raw = hmac.new(
            self.secret, b"mlchess-invitation-v1:" + invitation_id.bytes, hashlib.sha256
        ).digest()
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")

    @staticmethod
    def expires(invite):
        return (
            invite.expires_at
            if invite.expires_at.tzinfo
            else invite.expires_at.replace(tzinfo=timezone.utc)
        )

    def response(self, invite, actor_id, now):
        own = invite.creator_id == actor_id
        return {
            "schema_version": 1,
            "invite_id": str(invite.id),
            "game_id": str(invite.game_id),
            "state": "active"
            if invite.accepted_by
            else "expired"
            if self.expires(invite) <= now
            else "waiting",
            "expires_at": iso(self.expires(invite)),
            "created_by_current_user": own,
            "invite_url": self.url(invite.id) if own else None,
        }

    def url(self, invitation_id):
        return f"{self.public_origin}/play/friend?invite={invitation_id}#token={self.token(invitation_id)}"

    def replay(self, response):
        return {
            **response,
            "invite_url": self.url(UUID(response["invite_id"]))
            if response["created_by_current_user"]
            else None,
        }

    async def create(self, actor_id: UUID, key: UUID, game_id: UUID):
        scope, request_hash = (
            "invite:create",
            fingerprint("invite:create", {"game_id": str(game_id)}),
        )
        async with self.factory() as session, session.begin():
            await DurableGameService.lock_actor(session, actor_id)
            cached = await DurableGameService.receipt(
                session, actor_id, key, request_hash, scope
            )
            if cached:
                return self.replay(cached)
            game, state, players = await DurableGameService.load(
                session, game_id, actor_id, lock=True
            )
            if (
                game.mode != "friend"
                or game.status != "waiting"
                or not any(p.user_id == actor_id and p.side == "white" for p in players)
            ):
                raise PublicProblem(409)
            now = await DurableGameService.now(session)
            invite = await session.scalar(
                select(Invitation).where(
                    Invitation.game_id == game_id,
                    Invitation.accepted_by.is_(None),
                    Invitation.expires_at > now,
                )
            )
            if invite is None:
                count = await session.scalar(
                    select(func.count())
                    .select_from(Invitation)
                    .where(
                        Invitation.creator_id == actor_id,
                        Invitation.accepted_by.is_(None),
                        Invitation.expires_at > now,
                    )
                )
                if count >= 5:
                    raise PublicProblem(429)
                invite_id = uuid4()
                invite = Invitation(
                    id=invite_id,
                    game_id=game_id,
                    creator_id=actor_id,
                    invite_code_hash=hashlib.sha256(
                        self.token(invite_id).encode("ascii")
                    ).hexdigest(),
                    expires_at=now + timedelta(days=1),
                )
                session.add(invite)
                await session.flush()
            response = self.response(invite, actor_id, now)
            DurableGameService.remember(
                session,
                actor_id,
                key,
                request_hash,
                game_id,
                {**response, "invite_url": None},
                scope,
            )
            return response

    async def get(self, actor_id: UUID, invitation_id: UUID):
        async with self.factory() as session:
            invite = await session.get(Invitation, invitation_id)
            if invite is None:
                raise PublicProblem(404)
            if actor_id not in {invite.creator_id, invite.accepted_by}:
                raise PublicProblem(403)
            return self.response(
                invite, actor_id, await DurableGameService.now(session)
            )

    async def accept(self, actor_id: UUID, key: UUID, invitation_id: UUID, token: str):
        token_hash = hashlib.sha256(token.encode("ascii")).hexdigest()
        request_hash = fingerprint(
            "invite:accept", {"invite_id": str(invitation_id), "token_hash": token_hash}
        )
        async with self.factory() as session, session.begin():
            await DurableGameService.lock_actor(session, actor_id)
            reference = await session.get(Invitation, invitation_id)
            if reference is None:
                raise PublicProblem(404)
            game, state, players = await DurableGameService.load(
                session, reference.game_id, reference.creator_id, lock=True
            )
            invite = await session.scalar(
                select(Invitation)
                .where(Invitation.id == invitation_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            cached = await DurableGameService.receipt(
                session, actor_id, key, request_hash, str(game.id)
            )
            if cached:
                return cached
            if not hmac.compare_digest(invite.invite_code_hash, token_hash):
                raise PublicProblem(403)
            if actor_id == invite.creator_id:
                raise PublicProblem(403)
            if invite.accepted_by:
                if invite.accepted_by != actor_id:
                    raise PublicProblem(409)
            else:
                now = await DurableGameService.now(session)
                if (
                    self.expires(invite) <= now
                    or game.mode != "friend"
                    or game.status != "waiting"
                    or len(players) != 1
                ):
                    raise PublicProblem(409)
                invite.accepted_by, invite.accepted_at = actor_id, now
                player = GamePlayer(
                    game_id=game.id,
                    side="black",
                    kind="human",
                    user_id=actor_id,
                    joined_at=now,
                )
                session.add(player)
                domain = decode_domain(state.domain)
                clock = decode_clock(state.clock)
                if clock:
                    clock = ServerClock(
                        clock.white_remaining_ms,
                        clock.black_remaining_ms,
                        clock.increment_ms,
                        chess.WHITE,
                        now,
                    )
                DurableGameService.save(
                    game, state, replace(domain, version=domain.version + 1), clock, now
                )
                DurableGameService.status_event(session, game, state, clock, now)
            now = await DurableGameService.now(session)
            response = self.response(invite, actor_id, now)
            DurableGameService.remember(
                session, actor_id, key, request_hash, game.id, response, str(game.id)
            )
            return response
