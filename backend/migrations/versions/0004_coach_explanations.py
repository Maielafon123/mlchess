"""Durable principal-scoped coach jobs over verified analyses."""

from alembic import op
import sqlalchemy as sa

revision = "0004_coach_explanations"
down_revision = "0003_worker_jobs"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "coach_explanations",
        sa.Column(
            "id",
            sa.Uuid(),
            sa.ForeignKey("outbox_events.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "requester_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "analysis_id",
            sa.Uuid(),
            sa.ForeignKey("analyses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "game_id",
            sa.Uuid(),
            sa.ForeignKey("games.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("revision", sa.BigInteger(), nullable=False),
        sa.Column("ply", sa.Integer(), nullable=False),
        sa.Column("model_id", sa.String(80), nullable=False),
        sa.Column("prompt_version", sa.String(80), nullable=False),
        sa.Column("language", sa.String(2), nullable=False),
        sa.Column("level", sa.String(24), nullable=False),
        sa.Column("student_context_version", sa.String(120), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("fallback_used", sa.Boolean(), nullable=False),
        sa.Column("payload_json", sa.JSON()),
        sa.Column("error_code", sa.String(80)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "requester_id",
            "analysis_id",
            "model_id",
            "prompt_version",
            "language",
            "level",
            "student_context_version",
            name="uq_coach_request",
        ),
        sa.CheckConstraint(
            "status IN ('pending','ready','failed')", name="ck_coach_status"
        ),
        sa.CheckConstraint(
            "status <> 'ready' OR payload_json IS NOT NULL",
            name="ck_coach_ready_payload",
        ),
        sa.CheckConstraint(
            "status <> 'failed' OR error_code IS NOT NULL", name="ck_coach_failed_error"
        ),
    )
    op.create_index("ix_coach_game", "coach_explanations", ["game_id", "revision"])


def downgrade():
    raise RuntimeError(
        "Retain coaching audit history; roll back compatible application code or restore a verified backup"
    )
