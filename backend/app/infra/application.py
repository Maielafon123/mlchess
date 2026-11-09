"""Common ASGI policy for independently composed application services."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from sqlalchemy.ext.asyncio import AsyncEngine
from starlette.exceptions import HTTPException

from backend.app.infra.db import create_schema
from backend.app.infra.generated.contracts import HealthV1
from backend.app.infra.http import SafeHTTPMiddleware, default_request_logger
from backend.app.infra.metrics import MetricsRegistry
from backend.app.infra.problems import PublicProblem, problem_response
from backend.app.infra.settings import Settings

ReadinessCheck = Callable[[], Awaitable[None]]


def create_http_app(
    title: str,
    settings: Settings,
    *,
    engine: AsyncEngine | None = None,
    owns_engine: bool = False,
    readiness_checks: Sequence[ReadinessCheck] = (),
    logger: logging.Logger | None = None,
) -> FastAPI:
    checks = tuple(readiness_checks)
    if len(checks) > 8:
        raise ValueError("Readiness checks must be bounded")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            if engine is not None and settings.database_auto_create:
                await create_schema(engine)
            app.state.started = True
            yield
        finally:
            app.state.started = False
            if engine is not None and owns_engine:
                await engine.dispose()

    app = FastAPI(
        title=title,
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
