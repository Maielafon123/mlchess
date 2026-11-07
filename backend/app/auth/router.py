from __future__ import annotations

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, Field

from backend.app.infra.generated.contracts import CurrentUserV1
from backend.app.infra.problems import PublicProblem
from backend.app.infra.security import RateLimitExceeded

from .service import AuthService, AuthenticatedUser, now_utc
from backend.app.infra.generated.contracts import GuestSessionRequestV1

router = APIRouter(prefix="/api/v1", tags=["auth"])


class DevLoginRequest(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=80)


def public_user(user: AuthenticatedUser) -> CurrentUserV1:
    return CurrentUserV1(
        schema_version=1,
        id=str(user.id),
        kind=user.kind,
        display_name=user.display_name,
        expires_at=user.expires_at.isoformat().replace("+00:00", "Z"),
    )


def auth_service(request: Request) -> AuthService:
    return request.app.state.auth_service


def session_cookies(
    response: Response, request: Request, token: str, csrf: str, user: AuthenticatedUser
) -> None:
    secure = request.app.state.settings.public_origin.startswith("https://")
    max_age = max(0, int((user.expires_at - now_utc()).total_seconds()))
    response.set_cookie(
        "mlchess_session",
        token,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
        max_age=max_age,
    )
    response.set_cookie(
        "mlchess_csrf",
        csrf,
        httponly=False,
        secure=secure,
        samesite="lax",
        path="/",
        max_age=max_age,
    )


@router.post("/auth/guest", response_model=CurrentUserV1, operation_id="guestSession")
async def guest_session(
    payload: GuestSessionRequestV1, response: Response, request: Request
):
    if request.app.state.database_factory is None:
        raise PublicProblem(503)
    service = auth_service(request)
    previous = request.cookies.get("mlchess_session")
    record = await service.authenticate(previous)
    if record and service.valid_csrf(record, request.cookies.get("mlchess_csrf")):
        return public_user(record.user)
    client = request.client.host if request.client else "unknown"
    try:
        request.app.state.guest_login_limiter.check(client)
    except RateLimitExceeded:
        raise PublicProblem(429) from None
    if record:
        token, csrf, user = await service.issue_session(record.user)
        await service.revoke(previous)
    else:
        token, csrf, user = await service.issue_guest_session()
    session_cookies(response, request, token, csrf, user)
    return public_user(user)


async def current_session(request: Request):
    record = await auth_service(request).authenticate(
        request.cookies.get("mlchess_session")
    )
    if record is None:
        raise PublicProblem(401)
    return record


@router.post("/auth/dev-login", response_model=CurrentUserV1, operation_id="devLogin")
async def dev_login(payload: DevLoginRequest, response: Response, request: Request):
    if not request.app.state.settings.dev_auth_enabled:
        raise PublicProblem(404)
    client = request.client.host if request.client is not None else "unknown"
    try:
        request.app.state.dev_login_limiter.check(client)
    except RateLimitExceeded:
        raise PublicProblem(429) from None
    token, csrf, user = await auth_service(request).issue_dev_session(
        display_name=payload.display_name
    )
    session_cookies(response, request, token, csrf, user)
    return public_user(user)


@router.get("/me", response_model=CurrentUserV1, operation_id="currentUser")
async def me(request: Request):
    return public_user((await current_session(request)).user)


@router.post("/logout", status_code=204, operation_id="logout")
async def logout(response: Response, request: Request):
    record = await current_session(request)
    if not auth_service(request).valid_csrf(
        record, request.headers.get("x-csrf-token")
    ):
        raise PublicProblem(403)
    token = request.cookies.get("mlchess_session")
    assert token is not None
    await auth_service(request).revoke(token)
    response.delete_cookie("mlchess_session", path="/")
    response.delete_cookie("mlchess_csrf", path="/")
