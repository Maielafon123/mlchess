"""Persistent worker leases and audited engine move identity."""

from alembic import op
import sqlalchemy as sa

revision = "0003_worker_jobs"
down_revision = "0002_game_commands"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "worker_jobs",
        sa.Column(
            "id",
            sa.Uuid(),
            sa.ForeignKey("outbox_events.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "game_id",
            sa.Uuid(),
            sa.ForeignKey("games.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("queue", sa.String(16), nullable=False),
        sa.Column("expected_version", sa.BigInteger(), nullable=False),
        sa.Column("revision", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("lease_token", sa.Uuid()),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("failure_code", sa.String(40)),
        sa.Column("output", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "status IN ('pending','running','done','failed','stale')",
            name="ck_worker_job_status",
        ),
        sa.CheckConstraint("attempts >= 0", name="ck_worker_job_attempts"),
        sa.CheckConstraint(
            "(status = 'running' AND lease_token IS NOT NULL AND lease_until IS NOT NULL) OR (status <> 'running' AND lease_token IS NULL AND lease_until IS NULL)",
            name="ck_worker_job_lease",
        ),
    )
    op.create_index(
        "ix_worker_jobs_ready", "worker_jobs", ["queue", "status", "available_at"]
    )
    with op.batch_alter_table("game_moves") as batch:
        batch.add_column(
            sa.Column(
                "worker_job_id",
                sa.Uuid(),
                sa.ForeignKey(
                    "worker_jobs.id",
                    name="fk_game_move_worker",
                    ondelete="NO ACTION",
                    deferrable=True,
                    initially="DEFERRED",
                ),
            )
        )
        batch.alter_column("actor_id", existing_type=sa.Uuid(), nullable=True)
        batch.create_unique_constraint("uq_game_move_worker_job", ["worker_job_id"])
        batch.create_check_constraint(
            "ck_game_move_actor", "actor_id IS NOT NULL OR worker_job_id IS NOT NULL"
        )


def downgrade() -> None:
    raise RuntimeError(
        "Retain worker/move audit evidence and roll back compatible application code"
    )
