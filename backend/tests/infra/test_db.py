from __future__ import annotations

from backend.app.infra.db import create_engine, session_factory
from backend.app.infra.models import Base


def test_metadata_contains_required_tables_and_constraints():
    assert {
        "users",
        "sessions",
        "games",
        "game_players",
        "game_moves",
        "game_events",
        "invitations",
        "ratings",
        "analyses",
        "outbox_events",
    } <= set(Base.metadata.tables)
    assert {
        constraint.name for constraint in Base.metadata.tables["game_moves"].constraints
    } >= {"uq_game_move_idempotency"}
    assert {
        constraint.name
        for constraint in Base.metadata.tables["game_events"].constraints
    } >= {"uq_game_event_seq"}


def test_async_engine_and_session_factory_are_constructible():
    engine = create_engine("sqlite+aiosqlite:///./test.db")
    factory = session_factory(engine)
    assert factory.class_.__name__ == "AsyncSession"
