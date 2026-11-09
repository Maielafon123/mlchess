"""HTTP session, mutation and command identity dependencies shared by services."""

from __future__ import annotations

import re
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Path, Request

from backend.app.auth.cookies import session_token
from backend.app.auth.service import SessionRecord
from backend.app.infra.problems import PublicProblem
from backend.app.infra.security import RateLimitExceeded

UUID_PATTERN = r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
GameId = Annotated[str, Path(pattern=UUID_PATTERN)]


async def current_session(request: Request) -> SessionRecord:
    record = await request.app.state.auth_service.authenticate(session_token(request))
    if record is None:
        raise PublicProblem(401)
    return record


def require_csrf(request: Request, record: SessionRecord) -> None:
    values = request.headers.getlist("x-csrf-token")
    if len(values) != 1 or not request.app.state.auth_service.valid_csrf(
        record, values[0]
    ):
        raise PublicProblem(403)


async def writer(
    request: Request, record: Annotated[SessionRecord, Depends(current_session)]
):
    require_csrf(request, record)
    try:
        request.app.state.command_limiter.check(str(record.user.id))
    except RateLimitExceeded:
        raise PublicProblem(429) from None
    return record


def key(request: Request, value: str) -> UUID:
    if len(request.headers.getlist("idempotency-key")) != 1 or not re.fullmatch(
        UUID_PATTERN, value
    ):
        raise PublicProblem(422)
    return UUID(value)
