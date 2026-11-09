"""Shared wire timestamps and command fingerprints."""

from datetime import datetime, timezone
from hashlib import sha256
import json

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


def iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def fingerprint(operation: str, payload: dict) -> str:
    return sha256(
        json.dumps([operation, payload], sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


async def database_now(session: AsyncSession) -> datetime:
    if session.bind.dialect.name == "postgresql":
        # Transaction start time can precede a wait on a row or advisory lock.
        return await session.scalar(select(func.clock_timestamp()))
    return datetime.now(timezone.utc)
