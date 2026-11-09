"""Expose one minimum session projection to the restricted learning role."""

from alembic import op

revision = "0009_learning_boundary"
down_revision = "0008_google_oidc"
branch_labels = None
depends_on = None


def upgrade():
    if op.get_context().dialect.name != "postgresql":
        return
    op.execute("""
        CREATE FUNCTION public.mlchess_learning_session(p_hash text)
        RETURNS TABLE(user_id uuid, kind varchar, display_name varchar,
                      expires_at timestamptz, csrf_token_hash varchar)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog
        AS $$
          SELECT u.id, u.kind, u.display_name, s.expires_at, s.csrf_token_hash
          FROM public.sessions AS s JOIN public.users AS u ON u.id = s.user_id
          WHERE length(p_hash) = 64 AND s.token_hash = p_hash
            AND s.revoked_at IS NULL AND s.expires_at > statement_timestamp()
            AND u.deleted_at IS NULL
        $$;
    """)
    op.execute(
        "REVOKE ALL ON FUNCTION public.mlchess_learning_session(text) FROM PUBLIC"
    )


def downgrade():
    if op.get_context().dialect.name == "postgresql":
        op.execute("DROP FUNCTION public.mlchess_learning_session(text)")
