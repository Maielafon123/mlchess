"""Application composition for guarded HTTP, durable sessions and game commands."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Sequence
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine
from starlette.exceptions import HTTPException

from backend.app.auth.router import router as auth_router
from backend.app.analysis.durable import DurableAnalysisService
from backend.app.analysis.router import router as analysis_router
from backend.app.auth.service import (
    AuthService,
    InMemorySessionStore,
    SqlAlchemySessionStore,
)
from backend.app.games.durable import DurableGameService
from backend.app.games.router import router as games_router
from backend.app.games.invitation_router import router as invitation_router
from backend.app.games.invitation_service import InvitationService
from backend.app.infra.db import create_engine, create_schema, session_factory
from backend.app.infra.models import GameState, GameMove, WorkerJob, CoachExplanation
from backend.app.coach.router import create_durable_router
from backend.app.coach.durable import DurableCoachService
from backend.app.learning.router import create_durable_router as learning_router
from backend.app.learning.durable import DurableLearningService
from backend.app.realtime.durable import DurableEventStream
from backend.app.realtime.router import Connections, create_router as realtime_router
from backend.app.infra.models import LearningProfileRow, LessonRow
from backend.app.infra.generated.contracts import HealthV1
from backend.app.infra.http import SafeHTTPMiddleware, default_request_logger
from backend.app.infra.metrics import MetricsRegistry
from backend.app.infra.security import SlidingWindowLimiter
from backend.app.infra.problems import PublicProblem, problem_response
from backend.app.infra.settings import Settings

ReadinessCheck = Callable[[], Awaitable[None]]


def create_app(
    settings: Settings | None = None,
    *,
    readiness_checks: Sequence[ReadinessCheck] = (),
    logger: logging.Logger | None = None,
    database_engine: AsyncEngine | None = None,
) -> FastAPI:
    settings = settings if settings is not None else Settings()
    engine = database_engine
    if engine is None and settings.database_url:
        engine = create_engine(settings.database_url)
    factory = session_factory(engine) if engine is not None else None

    async def database_ready():
        async with factory() as session:
            await session.execute(select(GameState.game_id).limit(1))
            await session.execute(select(GameMove.worker_job_id).limit(1))
            await session.execute(select(WorkerJob).limit(1))
            await session.execute(select(CoachExplanation.id).limit(1))
            await session.execute(select(LearningProfileRow.student_id).limit(1))
            await session.execute(select(LessonRow.id).limit(1))

    async def persistence_required():
        raise RuntimeError("Deployed API persistence is not configured")

    checks = tuple(readiness_checks) + ((database_ready,) if factory else ())
    if not factory and settings.environment in {"staging", "production"}:
        checks += (persistence_required,)
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
            if engine is not None and database_engine is None:
                await engine.dispose()

    app = FastAPI(
        title="MLChess API",
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
    app.state.dev_login_limiter = SlidingWindowLimiter(limit=20, window_seconds=60)
    app.state.guest_login_limiter = SlidingWindowLimiter(limit=120, window_seconds=600)
    app.state.command_limiter = SlidingWindowLimiter(limit=120, window_seconds=60)
    app.state.auth_service = AuthService(
        SqlAlchemySessionStore(factory) if factory else InMemorySessionStore(),
        session_ttl_seconds=settings.session_ttl_seconds,
    )
    app.state.game_service = DurableGameService(factory) if factory else None
    app.state.analysis_service = DurableAnalysisService(factory) if factory else None
    app.state.coach_service = DurableCoachService(factory) if factory else None
    app.state.learning_service = DurableLearningService(factory) if factory else None
    app.state.event_stream = DurableEventStream(factory) if factory else None
    app.state.ws_connections = Connections()
    app.state.invitation_service = (
        InvitationService(
            factory,
            secret=settings.invitation_secret,
            public_origin=settings.public_origin,
        )
        if factory and settings.invitation_secret
        else None
    )
    app.state.database_factory = factory
    app.include_router(auth_router)
    app.include_router(games_router)
    app.include_router(analysis_router)
    app.include_router(invitation_router)
    app.include_router(create_durable_router())
    app.include_router(learning_router())
    app.include_router(realtime_router())
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
