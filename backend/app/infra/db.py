"""Async SQLAlchemy infrastructure shared by backend services."""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from .models import Base


def create_engine(database_url: str, *, echo: bool = False) -> AsyncEngine:
    """Create an engine without opening a connection during application import."""
    return create_async_engine(database_url, echo=echo, pool_pre_ping=True)


def session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


async def get_session(
    factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with factory() as session:
        yield session


async def create_schema(engine: AsyncEngine) -> None:
    """Testing/dev helper; production schema changes go through Alembic."""
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def dispose_engine(engine: AsyncEngine) -> None:
    await engine.dispose()
