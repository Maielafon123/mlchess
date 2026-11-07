"""SQLAlchemy 2 models for the first server-authoritative persistence slice."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Index,
    String,
    Uuid,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


UUIDType = Uuid(as_uuid=True)


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    external_subject: Mapped[str | None] = mapped_column(String(255), unique=True)
    display_name: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[UUID] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    csrf_token_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Game(Base):
    __tablename__ = "games"

    id: Mapped[UUID] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="waiting")
    version: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    revision: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    fen: Mapped[str] = mapped_column(String(100), nullable=False)
    ply: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    side_to_move: Mapped[str] = mapped_column(
        String(5), nullable=False, default="white"
    )
    result: Mapped[str | None] = mapped_column(String(5))
    termination: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class GamePlayer(Base):
    __tablename__ = "game_players"

    game_id: Mapped[UUID] = mapped_column(
        ForeignKey("games.id", ondelete="CASCADE"), primary_key=True
    )
    side: Mapped[str] = mapped_column(String(5), primary_key=True)
    kind: Mapped[str] = mapped_column(String(8), nullable=False)
    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class GameMove(Base):
    __tablename__ = "game_moves"
    __table_args__ = (
        UniqueConstraint(
            "game_id", "actor_id", "client_move_id", name="uq_game_move_idempotency"
        ),
        UniqueConstraint("worker_job_id", name="uq_game_move_worker_job"),
        CheckConstraint(
            "actor_id IS NOT NULL OR worker_job_id IS NOT NULL",
            name="ck_game_move_actor",
        ),
    )

    id: Mapped[UUID] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    game_id: Mapped[UUID] = mapped_column(
        ForeignKey("games.id", ondelete="CASCADE"), nullable=False
    )
    actor_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    worker_job_id: Mapped[UUID | None] = mapped_column(
        ForeignKey(
            "worker_jobs.id",
            name="fk_game_move_worker",
            ondelete="NO ACTION",
            deferrable=True,
            initially="DEFERRED",
        )
    )
    client_move_id: Mapped[UUID] = mapped_column(UUIDType, nullable=False)
    expected_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    ply: Mapped[int] = mapped_column(Integer, nullable=False)
    revision: Mapped[int] = mapped_column(BigInteger, nullable=False)
    uci: Mapped[str] = mapped_column(String(5), nullable=False)
    san: Mapped[str] = mapped_column(String(32), nullable=False)
    fen_after: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class GameEvent(Base):
    __tablename__ = "game_events"
    __table_args__ = (UniqueConstraint("game_id", "seq", name="uq_game_event_seq"),)

    id: Mapped[UUID] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    game_id: Mapped[UUID] = mapped_column(
        ForeignKey("games.id", ondelete="CASCADE"), nullable=False
    )
    seq: Mapped[int] = mapped_column(BigInteger, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class Invitation(Base):
    __tablename__ = "invitations"

    id: Mapped[UUID] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    game_id: Mapped[UUID] = mapped_column(
        ForeignKey("games.id", ondelete="CASCADE"), nullable=False
    )
    creator_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    invite_code_hash: Mapped[str] = mapped_column(
        String(128), unique=True, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    accepted_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Rating(Base):
    __tablename__ = "ratings"
    __table_args__ = (UniqueConstraint("user_id", "pool", name="uq_rating_user_pool"),)

    id: Mapped[UUID] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    pool: Mapped[str] = mapped_column(String(32), nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False, default=1200)
    deviation: Mapped[int] = mapped_column(Integer, nullable=False, default=350)
    games_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class Analysis(Base):
    __tablename__ = "analyses"
    __table_args__ = (
        UniqueConstraint(
            "game_id", "ply", "revision", "cache_key", name="uq_analysis_request"
        ),
    )

    id: Mapped[UUID] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    game_id: Mapped[UUID] = mapped_column(
        ForeignKey("games.id", ondelete="CASCADE"), nullable=False
    )
    ply: Mapped[int] = mapped_column(Integer, nullable=False)
    revision: Mapped[int] = mapped_column(BigInteger, nullable=False)
    cache_key: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    error_code: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class OutboxEvent(Base):
    __tablename__ = "outbox_events"

    id: Mapped[UUID] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    aggregate_type: Mapped[str] = mapped_column(String(32), nullable=False)
    aggregate_id: Mapped[UUID] = mapped_column(UUIDType, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class GameState(Base):
    """Complete replayable line and server configuration, locked with its game."""

    __tablename__ = "game_states"

    game_id: Mapped[UUID] = mapped_column(
        ForeignKey("games.id", ondelete="CASCADE"), primary_key=True
    )
    domain: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    clock: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    event_seq: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)


class CommandReceipt(Base):
    """Exact response per actor/resource/key; move IDs are scoped to a game."""

    __tablename__ = "command_receipts"
    __table_args__ = (Index("ix_command_receipts_game", "game_id"),)

    actor_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    scope: Mapped[str] = mapped_column(String(36), primary_key=True)
    command_key: Mapped[UUID] = mapped_column(UUIDType, primary_key=True)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    game_id: Mapped[UUID] = mapped_column(
        ForeignKey("games.id", ondelete="CASCADE"), nullable=False
    )
    response: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class WorkerJob(Base):
    """Durable execution/lease state, separate from broker publication ACKs."""

    __tablename__ = "worker_jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','running','done','failed','stale')",
            name="ck_worker_job_status",
        ),
        CheckConstraint("attempts >= 0", name="ck_worker_job_attempts"),
        CheckConstraint(
            "(status = 'running' AND lease_token IS NOT NULL AND lease_until IS NOT NULL) OR (status <> 'running' AND lease_token IS NULL AND lease_until IS NULL)",
            name="ck_worker_job_lease",
        ),
        Index("ix_worker_jobs_ready", "queue", "status", "available_at"),
    )
    id: Mapped[UUID] = mapped_column(
        ForeignKey("outbox_events.id", ondelete="CASCADE"), primary_key=True
    )
    game_id: Mapped[UUID] = mapped_column(
        ForeignKey("games.id", ondelete="CASCADE"), nullable=False
    )
    queue: Mapped[str] = mapped_column(String(16), nullable=False)
    expected_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    revision: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lease_token: Mapped[UUID | None] = mapped_column(UUIDType)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    failure_code: Mapped[str | None] = mapped_column(String(40))
    output: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
