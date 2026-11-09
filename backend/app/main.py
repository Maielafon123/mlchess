"""Application composition for guarded HTTP, durable sessions and game commands."""

from __future__ import annotations

import logging
from collections.abc import Sequence

from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from backend.app.auth.router import router as auth_router
from backend.app.auth.google import GoogleOIDC
from backend.app.auth.oidc_attempts import OAuthAttempts
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
from backend.app.infra.application import ReadinessCheck, create_http_app
from backend.app.infra.db import create_engine, session_factory
from backend.app.infra.generated.contracts import CoachProviderStatusV1
from backend.app.infra.models import (
    Game,
    GameState,
    GameMove,
    OAuthAttemptRow,
    WorkerJob,
    CoachExplanation,
)
from backend.app.coach.router import create_durable_router
from backend.app.coach.durable import DurableCoachService
from backend.app.coach.providers.rules import RulesCoachProvider
from backend.app.learning.router import create_durable_router as learning_router
from backend.app.learning.durable import DurableLearningService
from backend.app.realtime.durable import DurableEventStream
from backend.app.realtime.broker import broker_runtime
from backend.app.realtime.router import Connections, create_router as realtime_router
from backend.app.matchmaking.durable import DurableMatchmaking
from backend.app.matchmaking.router import router as matchmaking_router
from backend.app.infra.models import MatchTicketRow, RatingSettlementRow
from backend.app.infra.models import LearningProfileRow, LessonRow
from backend.app.infra.security import SlidingWindowLimiter
from backend.app.infra.settings import Settings


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
            await session.execute(select(GameState.clock_observed_at).limit(1))
            await session.execute(select(Game.clock_deadline_at).limit(1))
            await session.execute(select(GameMove.worker_job_id).limit(1))
            await session.execute(select(WorkerJob).limit(1))
            await session.execute(select(CoachExplanation.id).limit(1))
            if not settings.learning_split:
                await session.execute(select(LearningProfileRow.student_id).limit(1))
                await session.execute(select(LessonRow.id).limit(1))
            await session.execute(select(MatchTicketRow.id).limit(1))
            await session.execute(select(RatingSettlementRow.game_id).limit(1))
            if settings.google_client_id:
                await session.execute(select(OAuthAttemptRow.session_hash).limit(1))

    async def persistence_required():
        raise RuntimeError("Deployed API persistence is not configured")

    checks = tuple(readiness_checks) + ((database_ready,) if factory else ())
    if not factory and settings.environment in {"staging", "production"}:
        checks += (persistence_required,)
    app = create_http_app(
        "MLChess API",
        settings,
        engine=engine,
        owns_engine=database_engine is None,
        readiness_checks=checks,
        logger=logger,
        runtime=broker_runtime(settings.redis_url),
    )
    app.state.wakeups = None
    app.state.dev_login_limiter = SlidingWindowLimiter(limit=20, window_seconds=60)
    app.state.guest_login_limiter = SlidingWindowLimiter(limit=120, window_seconds=600)
    app.state.oidc_ip_limiter = SlidingWindowLimiter(limit=30, window_seconds=600)
    app.state.oidc_actor_limiter = SlidingWindowLimiter(limit=6, window_seconds=300)
    app.state.google_oidc = (
        GoogleOIDC(
            settings.google_client_id,
            settings.google_client_secret.get_secret_value(),
            settings.public_origin + "/api/v1/auth/oidc/callback",
        )
        if factory and settings.google_client_id
        else None
    )
    app.state.oauth_attempts = (
        OAuthAttempts(factory, settings.session_ttl_seconds)
        if app.state.google_oidc
        else None
    )
    app.state.command_limiter = SlidingWindowLimiter(limit=120, window_seconds=60)
    app.state.auth_service = AuthService(
        SqlAlchemySessionStore(factory) if factory else InMemorySessionStore(),
        session_ttl_seconds=settings.session_ttl_seconds,
    )
    app.state.game_service = DurableGameService(factory) if factory else None
    app.state.analysis_service = DurableAnalysisService(factory) if factory else None
    model_id = (
        "openai:" + settings.coach_openai_model
        if settings.coach_openai_model
        else RulesCoachProvider.model_id
    )
    app.state.coach_service = (
        DurableCoachService(factory, model_id=model_id) if factory else None
    )

    @app.get(
        "/api/v1/coach/provider",
        response_model=CoachProviderStatusV1,
        operation_id="getCoachProvider",
    )
    async def coach_provider():
        return CoachProviderStatusV1(
            schema_version=1, external=bool(settings.coach_openai_model)
        )

    app.state.learning_service = (
        DurableLearningService(factory)
        if factory and not settings.learning_split
        else None
    )
    app.state.event_stream = DurableEventStream(factory) if factory else None
    app.state.ws_connections = Connections()
    app.state.matchmaking_service = DurableMatchmaking(factory) if factory else None
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
    if not settings.learning_split:
        app.include_router(learning_router())
    app.include_router(realtime_router())
    app.include_router(matchmaking_router)
    return app
