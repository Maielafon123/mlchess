from __future__ import annotations

import hashlib
import hmac
import secrets
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.app.infra.models import Session as DbSession
from backend.app.infra.models import User


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("ascii")).hexdigest()


@dataclass(frozen=True)
class AuthenticatedUser:
    id: UUID
    kind: str
    display_name: str | None
    expires_at: datetime


@dataclass
class SessionRecord:
    token_hash: str
    csrf_token: str
    user: AuthenticatedUser
    expires_at: datetime
    revoked_at: datetime | None = None
    csrf_token_hash: str | None = None


class SessionStore(Protocol):
    async def put(self, record: SessionRecord) -> None: ...

    async def get(self, token_hash: str) -> SessionRecord | None: ...

    async def revoke(self, token_hash: str, when: datetime) -> None: ...


class InMemorySessionStore:
    """Explicitly bounded store for tests and development-only auth."""

    def __init__(self) -> None:
        self.records: dict[str, SessionRecord] = {}

    async def put(self, record: SessionRecord) -> None:
        self.records[record.token_hash] = record

    async def get(self, token_hash: str) -> SessionRecord | None:
        return self.records.get(token_hash)

    async def revoke(self, token_hash: str, when: datetime) -> None:
        record = self.records.get(token_hash)
        if record is not None:
            record.revoked_at = when


class SqlAlchemySessionStore:
    """Durable opaque-session store used by the production composition root."""

    def __init__(self, factory: async_sessionmaker[AsyncSession]) -> None:
        self.factory = factory

    async def put(self, record: SessionRecord) -> None:
        async with self.factory() as session:
            insert = (
                pg_insert
                if session.bind.dialect.name == "postgresql"
                else sqlite_insert
            )
            await session.execute(
                insert(User)
                .values(
                    id=record.user.id,
                    kind=record.user.kind,
                    display_name=record.user.display_name,
                    expires_at=record.user.expires_at,
                )
                .on_conflict_do_nothing(index_elements=[User.id])
            )
            session.add(
                DbSession(
                    user_id=record.user.id,
                    token_hash=record.token_hash,
                    csrf_token_hash=digest(record.csrf_token),
                    expires_at=record.expires_at,
                )
            )
            await session.commit()

    async def get(self, token_hash: str) -> SessionRecord | None:
        async with self.factory() as session:
            result = await session.execute(
                select(DbSession, User)
                .join(User, User.id == DbSession.user_id)
                .where(DbSession.token_hash == token_hash)
                .where(User.deleted_at.is_(None))
            )
            row = result.one_or_none()
            if row is None:
                return None
            db_session, user = row
            return SessionRecord(
                token_hash=db_session.token_hash,
                csrf_token="",
                user=AuthenticatedUser(
                    user.id, user.kind, user.display_name, _aware(db_session.expires_at)
                ),
                expires_at=_aware(db_session.expires_at),
                revoked_at=_aware(db_session.revoked_at)
                if db_session.revoked_at
                else None,
                csrf_token_hash=db_session.csrf_token_hash,
            )

    async def revoke(self, token_hash: str, when: datetime) -> None:
        async with self.factory() as session:
            await session.execute(
                update(DbSession)
                .where(DbSession.token_hash == token_hash)
                .values(revoked_at=when)
            )
            await session.commit()


class AuthService:
    def __init__(self, store: SessionStore, *, session_ttl_seconds: int = 3600) -> None:
        self.store = store
        self.session_ttl_seconds = session_ttl_seconds

    async def issue_dev_session(
        self, *, display_name: str | None = None
    ) -> tuple[str, str, AuthenticatedUser]:
        now = now_utc()
        expires_at = now + timedelta(seconds=self.session_ttl_seconds)
        user = AuthenticatedUser(
            id=(
                UUID(
                    bytes=hashlib.sha256(("dev:" + display_name).encode()).digest()[
                        :16
                    ],
                    version=4,
                )
                if display_name
                else UUID("00000000-0000-4000-8000-000000000001")
            ),
            kind="account",
            display_name=display_name or "Developer",
            expires_at=expires_at,
        )
        return await self.issue_session(user)

    async def issue_guest_session(self) -> tuple[str, str, AuthenticatedUser]:
        user = AuthenticatedUser(
            uuid4(), "guest", "Guest", now_utc() + timedelta(days=7)
        )
        return await self.issue_session(user)

    async def issue_session(
        self, user: AuthenticatedUser
    ) -> tuple[str, str, AuthenticatedUser]:
        expires_at = user.expires_at
        token = secrets.token_urlsafe(32)
        csrf = secrets.token_urlsafe(24)
        await self.store.put(
            SessionRecord(
                digest(token), csrf, user, expires_at, csrf_token_hash=digest(csrf)
            )
        )
        return token, csrf, user

    async def authenticate(self, token: str | None) -> SessionRecord | None:
        if not token or re.fullmatch(r"[A-Za-z0-9_-]{43}", token) is None:
            return None
        record = await self.store.get(digest(token))
        if record is None or record.revoked_at is not None:
            return None
        if record.expires_at <= now_utc():
            return None
        return record

    async def revoke(self, token: str) -> None:
        await self.store.revoke(digest(token), now_utc())

    @staticmethod
    def valid_csrf(record: SessionRecord, supplied: str | None) -> bool:
        if supplied is None or re.fullmatch(r"[A-Za-z0-9_-]{1,256}", supplied) is None:
            return False
        expected = record.csrf_token_hash or digest(record.csrf_token)
        return hmac.compare_digest(expected, digest(supplied))


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
