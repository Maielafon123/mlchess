"""Bound the relay query to committed unpublished outbox rows."""

from alembic import op
import sqlalchemy as sa

revision = "0010_outbox_relay"
down_revision = "0009_learning_boundary"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        "ix_outbox_pending",
        "outbox_events",
        ["created_at", "id"],
        postgresql_where=sa.text("published_at IS NULL"),
        sqlite_where=sa.text("published_at IS NULL"),
    )


def downgrade():
    op.drop_index("ix_outbox_pending", table_name="outbox_events")
