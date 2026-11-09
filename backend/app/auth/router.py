from __future__ import annotations

from fastapi import APIRouter, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
import re

from .cookies import (
    CSRF_COOKIE,
    HOST_SESSION,
    clear_session,
    secure_session,
    session_token,
    write_session,
)
from .google import GoogleLoginFailed
from .dependencies import current_session, require_csrf

from backend.app.infra.generated.contracts import (
    AuthProvidersV1,
    CurrentUserV1,
    GoogleLoginStartV1,
    GuestSessionRequestV1,
)
from backend.app.infra.problems import PublicProblem
from backend.app.infra.security import RateLimitExceeded, client_key

from .service import AuthService, AuthenticatedUser, now_utc

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
    max_age = max(0, int((user.expires_at - now_utc()).total_seconds()))
    write_session(response, request, token, csrf, max_age)


@router.post("/auth/guest", response_model=CurrentUserV1, operation_id="guestSession")
async def guest_session(
    payload: GuestSessionRequestV1, response: Response, request: Request
):
    if request.app.state.database_factory is None:
        raise PublicProblem(503)
    service = auth_service(request)
    previous = session_token(request)
    record = await service.authenticate(previous)
    csrf = request.cookies.get(CSRF_COOKIE)
    if record and service.valid_csrf(record, csrf):
        if secure_session(request) and HOST_SESSION not in request.cookies:
            session_cookies(response, request, previous, csrf, record.user)
        return public_user(record.user)
    try:
        request.app.state.guest_login_limiter.check(client_key(request))
    except RateLimitExceeded:
        raise PublicProblem(429) from None
    if record:
        token, csrf, user = await service.issue_session(record.user)
        await service.revoke(previous)
    else:
        token, csrf, user = await service.issue_guest_session()
    session_cookies(response, request, token, csrf, user)
    return public_user(user)


@router.post("/auth/dev-login", response_model=CurrentUserV1, operation_id="devLogin")
async def dev_login(payload: DevLoginRequest, response: Response, request: Request):
    if not request.app.state.settings.dev_auth_enabled:
        raise PublicProblem(404)
    try:
        request.app.state.dev_login_limiter.check(client_key(request))
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
    require_csrf(request, record)
    token = session_token(request)
    assert token is not None
    await auth_service(request).revoke(token)
    clear_session(response, request)


@router.get(
    "/auth/providers", response_model=AuthProvidersV1, operation_id="authProviders"
)
async def auth_providers(request: Request):
    return {"schema_version": 1, "google": request.app.state.google_oidc is not None}


@router.post(
    "/auth/oidc/start",
    response_model=GoogleLoginStartV1,
    operation_id="startGoogleLogin",
)
async def start_google(request: Request):
    provider = request.app.state.google_oidc
    if provider is None:
        raise PublicProblem(404)
    record = await current_session(request)
    require_csrf(request, record)
    try:
        request.app.state.oidc_ip_limiter.check(client_key(request))
        request.app.state.oidc_actor_limiter.check(str(record.user.id))
    except RateLimitExceeded:
        raise PublicProblem(429) from None
    state, nonce, challenge = await request.app.state.oauth_attempts.start(
        record.token_hash
    )
    return {
        "schema_version": 1,
        "authorization_url": provider.authorization_url(state, nonce, challenge),
    }


@router.get("/auth/oidc/callback", operation_id="finishGoogleLogin")
async def finish_google(request: Request):
    provider = request.app.state.google_oidc
    if provider is None:
        raise PublicProblem(404)

    def redirect(path: str):
        return RedirectResponse(
            path, status_code=303, headers={"Referrer-Policy": "no-referrer"}
        )

    failure = "/play?auth=google-failed"
    # Do not reflect provider errors, untrusted destinations or the code in a response.
    if len(request.scope.get("query_string", b"")) > 4096:
        return redirect(failure)
    params = request.query_params
    states, codes = params.getlist("state"), params.getlist("code")
    if len(states) != 1 or not re.fullmatch(r"[A-Za-z0-9_-]{43}", states[0]):
        return redirect(failure)
    record = await auth_service(request).authenticate(session_token(request))
    if record is None:
        return redirect(failure)
    attempts = request.app.state.oauth_attempts
    attempt = await attempts.consume(record.token_hash, states[0])
    if (
        attempt is None
        or "error" in params
        or len(codes) != 1
        or not re.fullmatch(r"[\x21-\x7e]{1,2048}", codes[0])
    ):
        return redirect(failure)
    try:
        verifier, nonce = attempt
        identity = await provider.identity(codes[0], verifier, nonce)
        token, csrf, user = await attempts.sign_in(record.token_hash, identity)
    except GoogleLoginFailed:
        return redirect(failure)
    response = redirect("/play")
    session_cookies(response, request, token, csrf, user)
    return response
