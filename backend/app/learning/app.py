"""Independent learning HTTP service; no gameplay or session issuance routes."""

from sqlalchemy import select, text

from backend.app.auth.service import (
    AuthenticatedUser,
    SessionAuthenticator,
    SessionRecord,
    SqlAlchemySessionStore,
)
from backend.app.infra.application import create_http_app
from backend.app.infra.db import create_engine, session_factory
from backend.app.infra.models import LearningProfileRow, LessonRow, PuzzleRow
from backend.app.infra.security import SlidingWindowLimiter
from backend.app.infra.settings import Settings
from backend.app.learning.durable import DurableLearningService
from backend.app.learning.router import create_durable_router


class ProjectedSessionReader:
    """Can verify a known token hash but cannot list or edit session records."""

    def __init__(self, factory):
        self.factory = factory

    async def get(self, token_hash):
        async with self.factory() as session:
            row = (
                await session.execute(
                    text("SELECT * FROM public.mlchess_learning_session(:token_hash)"),
                    {"token_hash": token_hash},
                )
            ).one_or_none()
        if row is None:
            return None
        return SessionRecord(
            token_hash,
            "",
            AuthenticatedUser(row.user_id, row.kind, row.display_name, row.expires_at),
            row.expires_at,
            csrf_token_hash=row.csrf_token_hash,
        )


def create_app(settings: Settings | None = None):
    settings = settings if settings is not None else Settings()
    if settings.database_url is None:
        raise ValueError("The learning service requires a database URL")
    postgres = settings.database_url.startswith("postgresql+asyncpg://")
    if postgres and not settings.database_url.startswith(
        "postgresql+asyncpg://mlchess_learning:"
    ):
        raise ValueError("The learning service must use the restricted PostgreSQL role")
    options = {"pool_size": 3, "max_overflow": 2, "pool_timeout": 2} if postgres else {}
    engine = create_engine(settings.database_url, **options)
    factory = session_factory(engine)
    reader = (
        ProjectedSessionReader(factory) if postgres else SqlAlchemySessionStore(factory)
    )

    async def database_ready():
        async with factory() as session:
            for table in (LessonRow, PuzzleRow, LearningProfileRow):
                await session.execute(select(table).limit(1))
        if postgres:
            await reader.get("0" * 64)

    app = create_http_app(
        "MLChess Learning",
        settings,
        engine=engine,
        owns_engine=True,
        readiness_checks=(database_ready,),
    )
    app.state.learning_service = DurableLearningService(factory)
    app.state.auth_service = SessionAuthenticator(reader)
    app.state.command_limiter = SlidingWindowLimiter(limit=120, window_seconds=60)
    app.include_router(create_durable_router())
    return app
