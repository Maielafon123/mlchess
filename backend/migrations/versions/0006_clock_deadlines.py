"""Index persisted game deadlines and retain the last observed server time."""

from alembic import op
import sqlalchemy as sa

revision = "0006_clock_deadlines"
down_revision = "0005_learning"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("games", sa.Column("clock_deadline_at", sa.DateTime(timezone=True)))
    op.add_column(
        "game_states", sa.Column("clock_observed_at", sa.DateTime(timezone=True))
    )
    dialect = op.get_context().dialect.name
    if dialect == "postgresql":
        op.execute("""
            UPDATE game_states
            SET clock_observed_at = (clock->>'anchor')::timestamptz
            WHERE clock->>'anchor' IS NOT NULL
        """)
        op.execute("""
            UPDATE games AS game
            SET clock_deadline_at = state.clock_observed_at +
                (CASE WHEN state.clock->>'running_side' = 'true'
                    THEN state.clock->>'white_remaining_ms'
                    ELSE state.clock->>'black_remaining_ms' END)::bigint * interval '1 millisecond'
            FROM game_states AS state
            WHERE state.game_id = game.id AND game.status = 'active'
                AND state.clock->>'running_side' IN ('true', 'false')
                AND state.clock_observed_at IS NOT NULL
        """)
    elif dialect == "sqlite":
        op.execute("""
            UPDATE game_states
            SET clock_observed_at = strftime('%Y-%m-%d %H:%M:%f', json_extract(clock, '$.anchor'))
            WHERE json_extract(clock, '$.anchor') IS NOT NULL
        """)
        op.execute("""
            UPDATE games
            SET clock_deadline_at = (
                SELECT strftime('%Y-%m-%d %H:%M:%f', state.clock_observed_at,
                    printf('+%f seconds', (CASE WHEN json_extract(state.clock, '$.running_side') = 1
                        THEN json_extract(state.clock, '$.white_remaining_ms')
                        ELSE json_extract(state.clock, '$.black_remaining_ms') END) / 1000.0))
                FROM game_states AS state
                WHERE state.game_id = games.id AND json_extract(state.clock, '$.running_side') IN (0, 1)
            )
            WHERE status = 'active'
        """)
    else:
        raise RuntimeError("Unsupported durable clock database")
    present = sa.text("clock_deadline_at IS NOT NULL")
    op.create_index(
        "ix_games_clock_deadline",
        "games",
        ["clock_deadline_at"],
        postgresql_where=present,
        sqlite_where=present,
    )


def downgrade():
    raise RuntimeError(
        "Retain clock watermarks; roll back compatible application images or restore"
    )
