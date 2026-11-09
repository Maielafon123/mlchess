"""One-use, browser-bound OAuth attempts and atomic session rotation."""

from __future__ import annotations

from base64 import urlsafe_b64encode
from datetime import timedelta
from hashlib import sha256
from secrets import token_urlsafe
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from backend.app.auth.google import GoogleIdentity, GoogleLoginFailed
from backend.app.auth.service import AuthenticatedUser, digest, now_utc, _aware
from backend.app.infra.models import OAuthAttemptRow, Session, User


def insert_for(session):
    return pg_insert if session.bind.dialect.name == "postgresql" else sqlite_insert


class OAuthAttempts:
    def __init__(self, factory, ttl: int):
        self.factory = factory
        self.ttl = ttl

    async def start(self, session_hash: str) -> tuple[str, str, str]:
        state, nonce, verifier = (token_urlsafe(32) for _ in range(3))
        now = now_utc()
        values = {
            "state_hash": digest(state),
            "nonce": nonce,
            "verifier": verifier,
            "expires_at": now + timedelta(minutes=5),
        }
        async with self.factory() as session, session.begin():
            await session.execute(
                delete(OAuthAttemptRow).where(OAuthAttemptRow.expires_at <= now)
            )
            await session.execute(
                insert_for(session)(OAuthAttemptRow)
                .values(session_hash=session_hash, **values)
                .on_conflict_do_update(
                    index_elements=[OAuthAttemptRow.session_hash], set_=values
                )
            )
        challenge = urlsafe_b64encode(sha256(verifier.encode("ascii")).digest())
        return state, nonce, challenge.rstrip(b"=").decode("ascii")

    async def consume(self, session_hash: str, state: str) -> tuple[str, str] | None:
        async with self.factory() as session, session.begin():
            row = (
                await session.execute(
                    delete(OAuthAttemptRow)
                    .where(
                        OAuthAttemptRow.session_hash == session_hash,
                        OAuthAttemptRow.state_hash == digest(state),
                        OAuthAttemptRow.expires_at > now_utc(),
                    )
                    .returning(OAuthAttemptRow.verifier, OAuthAttemptRow.nonce)
                )
            ).one_or_none()
            return (row.verifier, row.nonce) if row else None

    async def sign_in(
        self, previous_hash: str, identity: GoogleIdentity
    ) -> tuple[str, str, AuthenticatedUser]:
        token, csrf = token_urlsafe(32), token_urlsafe(24)
        async with self.factory() as session, session.begin():
            old = await session.scalar(
                select(Session)
                .where(Session.token_hash == previous_hash)
                .with_for_update()
            )
            now = now_utc()
            if (
                old is None
                or old.revoked_at is not None
                or _aware(old.expires_at) <= now
            ):
                raise GoogleLoginFailed
            await session.execute(
                insert_for(session)(User)
                .values(
                    id=uuid4(),
                    kind="account",
                    external_subject=identity.subject,
                    display_name=identity.name,
                )
                .on_conflict_do_nothing(index_elements=[User.external_subject])
            )
            user = await session.scalar(
                select(User)
                .where(User.external_subject == identity.subject)
                .with_for_update()
            )
            if user is None or user.deleted_at is not None or user.kind != "account":
                raise GoogleLoginFailed
            expires = now + timedelta(seconds=self.ttl)
            session.add(
                Session(
                    user_id=user.id,
                    token_hash=digest(token),
                    csrf_token_hash=digest(csrf),
                    expires_at=expires,
                )
            )
            old.revoked_at = now
            return (
                token,
                csrf,
                AuthenticatedUser(user.id, "account", user.display_name, expires),
            )
