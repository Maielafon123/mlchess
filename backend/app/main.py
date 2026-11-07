"""A-004 composition root; game/auth/engine handlers are added in later tickets."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Sequence
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException

from backend.app.auth.router import router as auth_router
from backend.app.auth.service import AuthService, InMemorySessionStore
from backend.app.coach.router import router as coach_router
from backend.app.learning.router import router as learning_router
from backend.app.infra.generated.contracts import HealthV1
from backend.app.infra.http import SafeHTTPMiddleware, default_request_logger
from backend.app.infra.metrics import MetricsRegistry
from backend.app.infra.problems import PublicProblem, problem_response
from backend.app.infra.settings import Settings

ReadinessCheck = Callable[[], Awaitable[None]]


def create_app(
    settings: Settings | None = None,
    *,
    readiness_checks: Sequence[ReadinessCheck] = (),
    logger: logging.Logger | None = None,
) -> FastAPI:
    settings = settings if settings is not None else Settings()
    checks = tuple(readiness_checks)
    if len(checks) > 8:
        raise ValueError("Readiness checks must be bounded")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.started = True
        try:
            yield
        finally:
            app.state.started = False

    app = FastAPI(
        title="MLChess backend scaffold",
        version="0.1.0",
        debug=False,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.state.started = False
    app.state.settings = settings
    app.state.metrics = MetricsRegistry()
    app.state.auth_service = AuthService(
        InMemorySessionStore(), session_ttl_seconds=settings.session_ttl_seconds
    )
    app.include_router(auth_router)
    app.include_router(coach_router)
    app.include_router(learning_router)
    app.add_middleware(
        SafeHTTPMiddleware,
        settings=settings,
        logger=logger if logger is not None else default_request_logger(),
        metrics=app.state.metrics,
    )

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        response = problem_response(exc.status_code, request.state.request_id)
        if exc.status_code == 405 and exc.headers and "Allow" in exc.headers:
            response.headers["Allow"] = exc.headers["Allow"]
        return response

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, exc: RequestValidationError):
        return problem_response(422, request.state.request_id)

    @app.exception_handler(PublicProblem)
    async def public_error(request: Request, exc: PublicProblem):
        return problem_response(exc.status, request.state.request_id)

    @app.get("/health/live", response_model=HealthV1, operation_id="healthLive")
    async def live():
        return HealthV1(schema_version=1, status="ok")

    @app.get("/health/ready", response_model=HealthV1, operation_id="healthReady")
    async def ready(request: Request):
        if not app.state.started:
            return problem_response(503, request.state.request_id)
        try:
            async with asyncio.timeout(settings.readiness_timeout_ms / 1000):
                for check in checks:
                    if await check() is not None:
                        raise ValueError("Readiness checks must return None on success")
        except Exception:
            return problem_response(503, request.state.request_id)
        return HealthV1(schema_version=1, status="ok")

    return app
