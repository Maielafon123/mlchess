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
    text,
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


class OAuthAttemptRow(Base):
    __tablename__ = "oauth_attempts"
    __table_args__ = (Index("ix_oauth_attempt_expiry", "expires_at"),)

    session_hash: Mapped[str] = mapped_column(
        ForeignKey("sessions.token_hash", ondelete="CASCADE"), primary_key=True
    )
    state_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    nonce: Mapped[str] = mapped_column(String(43), nullable=False)
    verifier: Mapped[str] = mapped_column(String(43), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class Game(Base):
    __tablename__ = "games"
    __table_args__ = (
        Index(
            "ix_games_clock_deadline",
            "clock_deadline_at",
            postgresql_where=text("clock_deadline_at IS NOT NULL"),
            sqlite_where=text("clock_deadline_at IS NOT NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="waiting")
    clock_deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
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


class MatchTicketRow(Base):
    __tablename__ = "matchmaking_tickets"
    __table_args__ = (
        CheckConstraint(
            "status IN ('searching','matched','cancelled','expired')",
            name="ck_match_ticket_status",
        ),
        CheckConstraint(
            "(status = 'matched' AND game_id IS NOT NULL) OR (status <> 'matched' AND game_id IS NULL)",
            name="ck_match_ticket_game",
        ),
        CheckConstraint(
            "rating BETWEEN 100 AND 4000 AND expires_at > queued_at",
            name="ck_match_ticket_values",
        ),
        UniqueConstraint("user_id", "game_id", name="uq_match_ticket_user_game"),
        Index(
            "uq_match_ticket_live_user",
            "user_id",
            unique=True,
            postgresql_where=text("status = 'searching'"),
            sqlite_where=text("status = 'searching'"),
        ),
        Index("ix_match_ticket_pool_queue", "pool", "status", "queued_at"),
        Index("ix_match_ticket_user_queue", "user_id", "queued_at"),
    )
    id: Mapped[UUID] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    game_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("games.id", ondelete="CASCADE")
    )
    pool: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class MatchReceiptRow(Base):
    __tablename__ = "matchmaking_receipts"
    __table_args__ = (Index("ix_match_receipt_user_time", "user_id", "created_at"),)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    command_key: Mapped[UUID] = mapped_column(UUIDType, primary_key=True)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    response: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class RatingSettlementRow(Base):
    __tablename__ = "rating_settlements"
    __table_args__ = (
        CheckConstraint(
            "result IN ('white','black','draw') AND white_id <> black_id",
            name="ck_rating_settlement_result",
        ),
        CheckConstraint(
            "white_before BETWEEN 100 AND 4000 AND black_before BETWEEN 100 AND 4000 AND white_after BETWEEN 100 AND 4000 AND black_after BETWEEN 100 AND 4000 AND white_before + black_before = white_after + black_after AND white_games >= 1 AND black_games >= 1",
            name="ck_rating_settlement_values",
        ),
    )
    game_id: Mapped[UUID] = mapped_column(
        ForeignKey("games.id", ondelete="CASCADE"), primary_key=True
    )
    pool: Mapped[str] = mapped_column(String(32), nullable=False)
    result: Mapped[str] = mapped_column(String(8), nullable=False)
    white_id: Mapped[UUID] = mapped_column(UUIDType, nullable=False)
    black_id: Mapped[UUID] = mapped_column(UUIDType, nullable=False)
    white_before: Mapped[int] = mapped_column(Integer, nullable=False)
    black_before: Mapped[int] = mapped_column(Integer, nullable=False)
    white_after: Mapped[int] = mapped_column(Integer, nullable=False)
    black_after: Mapped[int] = mapped_column(Integer, nullable=False)
    white_games: Mapped[int] = mapped_column(Integer, nullable=False)
    black_games: Mapped[int] = mapped_column(Integer, nullable=False)
    settled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
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
    __table_args__ = (
        Index(
            "ix_outbox_pending",
            "created_at",
            "id",
            postgresql_where=text("published_at IS NULL"),
            sqlite_where=text("published_at IS NULL"),
        ),
    )

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
    clock_observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
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


class CoachExplanation(Base):
    __tablename__ = "coach_explanations"
    __table_args__ = (
        UniqueConstraint(
            "requester_id",
            "analysis_id",
            "model_id",
            "prompt_version",
            "language",
            "level",
            "student_context_version",
            name="uq_coach_request",
        ),
        CheckConstraint(
            "status IN ('pending','ready','failed')", name="ck_coach_status"
        ),
        CheckConstraint(
            "status <> 'ready' OR payload_json IS NOT NULL",
            name="ck_coach_ready_payload",
        ),
        CheckConstraint(
            "status <> 'failed' OR error_code IS NOT NULL", name="ck_coach_failed_error"
        ),
        Index("ix_coach_game", "game_id", "revision"),
    )
    id: Mapped[UUID] = mapped_column(
        ForeignKey("outbox_events.id", ondelete="CASCADE"), primary_key=True
    )
    requester_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    analysis_id: Mapped[UUID] = mapped_column(
        ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False
    )
    game_id: Mapped[UUID] = mapped_column(
        ForeignKey("games.id", ondelete="CASCADE"), nullable=False
    )
    revision: Mapped[int] = mapped_column(BigInteger, nullable=False)
    ply: Mapped[int] = mapped_column(Integer, nullable=False)
    model_id: Mapped[str] = mapped_column(String(80), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(80), nullable=False)
    language: Mapped[str] = mapped_column(String(2), nullable=False)
    level: Mapped[str] = mapped_column(String(24), nullable=False)
    student_context_version: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    fallback_used: Mapped[bool] = mapped_column(nullable=False, default=False)
    payload_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    error_code: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


class LearningProfileRow(Base):
    __tablename__ = "learning_profiles"
    __table_args__ = (CheckConstraint("epoch >= 0", name="ck_learning_epoch"),)
    student_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    epoch: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)


class LessonRow(Base):
    __tablename__ = "lessons"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    content: Mapped[dict] = mapped_column(JSON, nullable=False)
    tags: Mapped[list] = mapped_column(JSON, nullable=False)
    source_name: Mapped[str] = mapped_column(String(200), nullable=False)
    source_url: Mapped[str] = mapped_column(String(500), nullable=False)
    license: Mapped[str] = mapped_column(String(120), nullable=False)


class PuzzleRow(Base):
    __tablename__ = "puzzles"
    __table_args__ = (
        CheckConstraint("difficulty BETWEEN 1 AND 5", name="ck_puzzle_difficulty"),
    )
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    fen: Mapped[str] = mapped_column(String(120), nullable=False)
    difficulty: Mapped[int] = mapped_column(Integer, nullable=False)
    tags: Mapped[list] = mapped_column(JSON, nullable=False)
    private_solution: Mapped[list] = mapped_column(JSON, nullable=False)
    solution_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    hints: Mapped[dict] = mapped_column(JSON, nullable=False)
    source_name: Mapped[str] = mapped_column(String(200), nullable=False)
    source_url: Mapped[str] = mapped_column(String(500), nullable=False)
    license: Mapped[str] = mapped_column(String(120), nullable=False)


class LessonProgressRow(Base):
    __tablename__ = "lesson_progress"
    __table_args__ = (
        CheckConstraint(
            "status IN ('started','completed')", name="ck_lesson_progress_status"
        ),
    )
    student_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    lesson_id: Mapped[str] = mapped_column(
        ForeignKey("lessons.id", ondelete="CASCADE"), primary_key=True
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


class PuzzleStateRow(Base):
    __tablename__ = "puzzle_states"
    __table_args__ = (
        CheckConstraint(
            "cursor >= 0 AND hints_count >= 0 AND hints_accounted >= 0 AND hints_accounted <= hints_count AND session_number >= 0",
            name="ck_puzzle_state_counters",
        ),
    )
    student_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    puzzle_id: Mapped[str] = mapped_column(
        ForeignKey("puzzles.id", ondelete="CASCADE"), primary_key=True
    )
    fen: Mapped[str] = mapped_column(String(120), nullable=False)
    history: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    cursor: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    hints_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    hints_accounted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    session_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


class PuzzleAttemptRow(Base):
    __tablename__ = "puzzle_attempts"
    __table_args__ = (
        Index("ix_puzzle_attempt_student_time", "student_id", "created_at"),
    )
    student_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    attempt_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    uci: Mapped[str] = mapped_column(String(5), nullable=False)
    puzzle_id: Mapped[str] = mapped_column(
        ForeignKey("puzzles.id", ondelete="CASCADE"), nullable=False
    )
    session_number: Mapped[int] = mapped_column(Integer, nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    response: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


class StudentSkillRow(Base):
    __tablename__ = "student_skills"
    __table_args__ = (
        CheckConstraint(
            "attempts >= 0 AND correct >= 0 AND correct <= attempts AND hints_used >= 0 AND streak >= 0 AND streak <= correct",
            name="ck_student_skill_counters",
        ),
    )
    student_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    skill: Mapped[str] = mapped_column(String(80), primary_key=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    correct: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    hints_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    streak: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProgressEventRow(Base):
    __tablename__ = "progress_events"
    student_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    event_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    skill: Mapped[str] = mapped_column(String(80), nullable=False)
    result: Mapped[str] = mapped_column(String(16), nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


class LearningReceiptRow(Base):
    __tablename__ = "learning_receipts"
    __table_args__ = (
        Index("ix_learning_receipt_student_time", "student_id", "created_at"),
    )
    student_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    command_key: Mapped[UUID] = mapped_column(UUIDType, primary_key=True)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    response: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
