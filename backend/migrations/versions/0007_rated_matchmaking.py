"""Durable account queue receipts and one immutable settlement per rated game."""

from alembic import op
import sqlalchemy as sa

revision = "0007_rated_matchmaking"
down_revision = "0006_clock_deadlines"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "matchmaking_tickets",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("game_id", sa.Uuid(), sa.ForeignKey("games.id", ondelete="CASCADE")),
        sa.Column("pool", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('searching','matched','cancelled','expired')",
            name="ck_match_ticket_status",
        ),
        sa.CheckConstraint(
            "(status = 'matched' AND game_id IS NOT NULL) OR (status <> 'matched' AND game_id IS NULL)",
            name="ck_match_ticket_game",
        ),
        sa.CheckConstraint(
            "rating BETWEEN 100 AND 4000 AND expires_at > queued_at",
            name="ck_match_ticket_values",
        ),
        sa.UniqueConstraint("user_id", "game_id", name="uq_match_ticket_user_game"),
    )
    live = sa.text("status = 'searching'")
    op.create_index(
        "uq_match_ticket_live_user",
        "matchmaking_tickets",
        ["user_id"],
        unique=True,
        postgresql_where=live,
        sqlite_where=live,
    )
    op.create_index(
        "ix_match_ticket_pool_queue",
        "matchmaking_tickets",
        ["pool", "status", "queued_at"],
    )
    op.create_index(
        "ix_match_ticket_user_queue", "matchmaking_tickets", ["user_id", "queued_at"]
    )
    op.create_table(
        "matchmaking_receipts",
        sa.Column(
            "user_id",
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
        "ix_match_receipt_user_time", "matchmaking_receipts", ["user_id", "created_at"]
    )
    op.create_table(
        "rating_settlements",
        sa.Column(
            "game_id",
            sa.Uuid(),
            sa.ForeignKey("games.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("pool", sa.String(32), nullable=False),
        sa.Column("result", sa.String(8), nullable=False),
        sa.Column("white_id", sa.Uuid(), nullable=False),
        sa.Column("black_id", sa.Uuid(), nullable=False),
        sa.Column("white_before", sa.Integer(), nullable=False),
        sa.Column("black_before", sa.Integer(), nullable=False),
        sa.Column("white_after", sa.Integer(), nullable=False),
        sa.Column("black_after", sa.Integer(), nullable=False),
        sa.Column("white_games", sa.Integer(), nullable=False),
        sa.Column("black_games", sa.Integer(), nullable=False),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "result IN ('white','black','draw') AND white_id <> black_id",
            name="ck_rating_settlement_result",
        ),
        sa.CheckConstraint(
            "white_before BETWEEN 100 AND 4000 AND black_before BETWEEN 100 AND 4000 AND white_after BETWEEN 100 AND 4000 AND black_after BETWEEN 100 AND 4000 AND white_before + black_before = white_after + black_after AND white_games >= 1 AND black_games >= 1",
            name="ck_rating_settlement_values",
        ),
    )


def downgrade():
    raise RuntimeError(
        "Retain rated history; roll back compatible application images or restore"
    )
