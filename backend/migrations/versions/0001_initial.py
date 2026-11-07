"""Initial server-authoritative persistence schema."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

uuid = sa.Uuid(as_uuid=True)
timestamp = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table("users", sa.Column("id", uuid, primary_key=True), sa.Column("kind", sa.String(16), nullable=False), sa.Column("external_subject", sa.String(255), unique=True), sa.Column("display_name", sa.String(120)), sa.Column("created_at", timestamp, nullable=False), sa.Column("expires_at", timestamp), sa.Column("deleted_at", timestamp))
    op.create_table("sessions", sa.Column("id", uuid, primary_key=True), sa.Column("user_id", uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("token_hash", sa.String(128), nullable=False, unique=True), sa.Column("csrf_token_hash", sa.String(128), nullable=False), sa.Column("created_at", timestamp, nullable=False), sa.Column("expires_at", timestamp, nullable=False), sa.Column("revoked_at", timestamp))
    op.create_table("games", sa.Column("id", uuid, primary_key=True), sa.Column("mode", sa.String(16), nullable=False), sa.Column("status", sa.String(16), nullable=False), sa.Column("version", sa.BigInteger, nullable=False), sa.Column("revision", sa.BigInteger, nullable=False), sa.Column("fen", sa.String(100), nullable=False), sa.Column("ply", sa.Integer, nullable=False), sa.Column("side_to_move", sa.String(5), nullable=False), sa.Column("result", sa.String(5)), sa.Column("termination", sa.String(32)), sa.Column("created_at", timestamp, nullable=False), sa.Column("updated_at", timestamp, nullable=False))
    op.create_table("game_players", sa.Column("game_id", uuid, sa.ForeignKey("games.id", ondelete="CASCADE"), primary_key=True), sa.Column("side", sa.String(5), primary_key=True), sa.Column("kind", sa.String(8), nullable=False), sa.Column("user_id", uuid, sa.ForeignKey("users.id", ondelete="SET NULL")), sa.Column("joined_at", timestamp, nullable=False))
    op.create_table("game_moves", sa.Column("id", uuid, primary_key=True), sa.Column("game_id", uuid, sa.ForeignKey("games.id", ondelete="CASCADE"), nullable=False), sa.Column("actor_id", uuid, sa.ForeignKey("users.id"), nullable=False), sa.Column("client_move_id", uuid, nullable=False), sa.Column("expected_version", sa.BigInteger, nullable=False), sa.Column("version", sa.BigInteger, nullable=False), sa.Column("ply", sa.Integer, nullable=False), sa.Column("revision", sa.BigInteger, nullable=False), sa.Column("uci", sa.String(5), nullable=False), sa.Column("san", sa.String(32), nullable=False), sa.Column("fen_after", sa.String(100), nullable=False), sa.Column("created_at", timestamp, nullable=False), sa.UniqueConstraint("game_id", "actor_id", "client_move_id", name="uq_game_move_idempotency"))
    op.create_table("game_events", sa.Column("id", uuid, primary_key=True), sa.Column("game_id", uuid, sa.ForeignKey("games.id", ondelete="CASCADE"), nullable=False), sa.Column("seq", sa.BigInteger, nullable=False), sa.Column("event_type", sa.String(64), nullable=False), sa.Column("payload", sa.JSON, nullable=False), sa.Column("created_at", timestamp, nullable=False), sa.UniqueConstraint("game_id", "seq", name="uq_game_event_seq"))
    op.create_table("invitations", sa.Column("id", uuid, primary_key=True), sa.Column("game_id", uuid, sa.ForeignKey("games.id", ondelete="CASCADE"), nullable=False), sa.Column("creator_id", uuid, sa.ForeignKey("users.id"), nullable=False), sa.Column("invite_code_hash", sa.String(128), nullable=False, unique=True), sa.Column("expires_at", timestamp, nullable=False), sa.Column("accepted_by", uuid, sa.ForeignKey("users.id")), sa.Column("accepted_at", timestamp))
    op.create_table("ratings", sa.Column("id", uuid, primary_key=True), sa.Column("user_id", uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("pool", sa.String(32), nullable=False), sa.Column("rating", sa.Integer, nullable=False), sa.Column("deviation", sa.Integer, nullable=False), sa.Column("games_count", sa.Integer, nullable=False), sa.Column("updated_at", timestamp, nullable=False), sa.UniqueConstraint("user_id", "pool", name="uq_rating_user_pool"))
    op.create_table("analyses", sa.Column("id", uuid, primary_key=True), sa.Column("game_id", uuid, sa.ForeignKey("games.id", ondelete="CASCADE"), nullable=False), sa.Column("ply", sa.Integer, nullable=False), sa.Column("revision", sa.BigInteger, nullable=False), sa.Column("cache_key", sa.String(128), nullable=False), sa.Column("status", sa.String(16), nullable=False), sa.Column("result", sa.JSON), sa.Column("error_code", sa.String(64)), sa.Column("created_at", timestamp, nullable=False), sa.Column("updated_at", timestamp, nullable=False), sa.UniqueConstraint("game_id", "ply", "revision", "cache_key", name="uq_analysis_request"))
    op.create_table("outbox_events", sa.Column("id", uuid, primary_key=True), sa.Column("aggregate_type", sa.String(32), nullable=False), sa.Column("aggregate_id", uuid, nullable=False), sa.Column("event_type", sa.String(64), nullable=False), sa.Column("payload", sa.JSON, nullable=False), sa.Column("attempts", sa.Integer, nullable=False), sa.Column("published_at", timestamp), sa.Column("created_at", timestamp, nullable=False))


def downgrade() -> None:
    for table in ("outbox_events", "analyses", "ratings", "invitations", "game_events", "game_moves", "game_players", "games", "sessions", "users"):
        op.drop_table(table)
