"""SQLAlchemy proposal for A's single Alembic migration.

This file defines metadata only. It does not create tables or connect to a DB.
The unique key includes student_context_version so cache and DB dedup remain
aligned with architecture v1.
"""

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
)

metadata = MetaData()

coach_explanations = Table(
    "coach_explanations",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("analysis_id", String(36), nullable=False),
    Column("game_id", String(36), nullable=False),
    Column("revision", Integer, nullable=False),
    Column("ply", Integer, nullable=False),
    Column("model_id", String(160), nullable=False),
    Column("prompt_version", String(80), nullable=False),
    Column("language", String(8), nullable=False),
    Column("level", String(32), nullable=False),
    Column("student_context_version", String(120), nullable=True),
    Column("status", String(16), nullable=False),
    Column("fallback_used", Boolean, nullable=False, default=False),
    Column("payload_json", String, nullable=True),
    Column("error_code", String(80), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint(
        "analysis_id",
        "model_id",
        "prompt_version",
        "language",
        "level",
        "student_context_version",
        name="uq_coach_explanation_request",
    ),
)
