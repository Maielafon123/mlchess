"""Durable full-history game state and command receipts (expand-only)."""

from alembic import op
import sqlalchemy as sa

revision = "0002_game_commands"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "game_states",
        sa.Column(
            "game_id",
            sa.Uuid(),
            sa.ForeignKey("games.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("domain", sa.JSON(), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("clock", sa.JSON()),
        sa.Column("event_seq", sa.BigInteger(), nullable=False, server_default="0"),
    )
    op.create_table(
        "command_receipts",
        sa.Column(
            "actor_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("scope", sa.String(36), primary_key=True),
        sa.Column("command_key", sa.Uuid(), primary_key=True),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column(
            "game_id",
            sa.Uuid(),
            sa.ForeignKey("games.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("response", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_command_receipts_game", "command_receipts", ["game_id"])


def downgrade() -> None:
    # Old snapshots have no durable domain state; dropping it would lose history.
    raise RuntimeError("Use an application rollback with the expanded schema retained")
