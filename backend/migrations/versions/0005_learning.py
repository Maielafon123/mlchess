"""Persistent learning content, private cursors, attempts and atomic progress."""

import json
from pathlib import Path

from alembic import op
import sqlalchemy as sa

revision = "0005_learning"
down_revision = "0004_coach_explanations"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "learning_profiles",
        sa.Column(
            "student_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("epoch", sa.BigInteger(), nullable=False),
        sa.CheckConstraint("epoch >= 0", name="ck_learning_epoch"),
    )
    lessons = op.create_table(
        "lessons",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("source_name", sa.String(200), nullable=False),
        sa.Column("source_url", sa.String(500), nullable=False),
        sa.Column("license", sa.String(120), nullable=False),
    )
    puzzles = op.create_table(
        "puzzles",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("fen", sa.String(120), nullable=False),
        sa.Column("difficulty", sa.Integer(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("private_solution", sa.JSON(), nullable=False),
        sa.Column("solution_digest", sa.String(64), nullable=False),
        sa.Column("hints", sa.JSON(), nullable=False),
        sa.Column("source_name", sa.String(200), nullable=False),
        sa.Column("source_url", sa.String(500), nullable=False),
        sa.Column("license", sa.String(120), nullable=False),
        sa.CheckConstraint("difficulty BETWEEN 1 AND 5", name="ck_puzzle_difficulty"),
    )
    op.create_table(
        "lesson_progress",
        sa.Column(
            "student_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "lesson_id",
            sa.String(80),
            sa.ForeignKey("lessons.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('started','completed')", name="ck_lesson_progress_status"
        ),
    )
    op.create_table(
        "puzzle_states",
        sa.Column(
            "student_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "puzzle_id",
            sa.String(80),
            sa.ForeignKey("puzzles.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("fen", sa.String(120), nullable=False),
        sa.Column("history", sa.JSON(), nullable=False),
        sa.Column("cursor", sa.Integer(), nullable=False),
        sa.Column("hints_count", sa.Integer(), nullable=False),
        sa.Column("hints_accounted", sa.Integer(), nullable=False),
        sa.Column("session_number", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "cursor >= 0 AND hints_count >= 0 AND hints_accounted >= 0 AND hints_accounted <= hints_count AND session_number >= 0",
            name="ck_puzzle_state_counters",
        ),
    )
    op.create_table(
        "puzzle_attempts",
        sa.Column(
            "student_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("attempt_id", sa.String(120), primary_key=True),
        sa.Column("uci", sa.String(5), nullable=False),
        sa.Column(
            "puzzle_id",
            sa.String(80),
            sa.ForeignKey("puzzles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("session_number", sa.Integer(), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("response", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_puzzle_attempt_student_time",
        "puzzle_attempts",
        ["student_id", "created_at"],
    )
    op.create_table(
        "student_skills",
        sa.Column(
            "student_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("skill", sa.String(80), primary_key=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("correct", sa.Integer(), nullable=False),
        sa.Column("hints_used", sa.Integer(), nullable=False),
        sa.Column("streak", sa.Integer(), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "attempts >= 0 AND correct >= 0 AND correct <= attempts AND hints_used >= 0 AND streak >= 0 AND streak <= correct",
            name="ck_student_skill_counters",
        ),
    )
    op.create_table(
        "progress_events",
        sa.Column(
            "student_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("event_id", sa.String(120), primary_key=True),
        sa.Column("skill", sa.String(80), nullable=False),
        sa.Column("result", sa.String(16), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "learning_receipts",
        sa.Column(
            "student_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("command_key", sa.Uuid(), primary_key=True),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("response", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_learning_receipt_student_time",
        "learning_receipts",
        ["student_id", "created_at"],
    )
    seed = json.loads(
        (Path(__file__).resolve().parents[1] / "data/0005_catalog.json").read_text(
            encoding="utf-8"
        )
    )
    # Frozen static seed JSON becomes SQL literals, also supported in offline/SQLite mode.
    for table, rows in ((lessons, seed["lessons"]), (puzzles, seed["puzzles"])):
        for row in rows:
            values = {
                key: (
                    sa.literal_column(
                        "'"
                        + json.dumps(value, ensure_ascii=False).replace("'", "''")
                        + "'"
                    )
                    if isinstance(value, (dict, list))
                    else value
                )
                for key, value in row.items()
            }
            op.execute(table.insert().values(**values))


def downgrade():
    raise RuntimeError(
        "Retain learning history; roll back compatible application code or restore a verified backup"
    )
