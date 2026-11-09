"""Store short-lived OAuth attempts bound to opaque browser sessions."""

from alembic import op
import sqlalchemy as sa

revision = "0008_google_oidc"
down_revision = "0007_rated_matchmaking"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "oauth_attempts",
        sa.Column(
            "session_hash",
            sa.String(128),
            sa.ForeignKey("sessions.token_hash", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("state_hash", sa.String(64), nullable=False),
        sa.Column("nonce", sa.String(43), nullable=False),
        sa.Column("verifier", sa.String(43), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_oauth_attempt_expiry", "oauth_attempts", ["expires_at"])


def downgrade():
    op.drop_table("oauth_attempts")
