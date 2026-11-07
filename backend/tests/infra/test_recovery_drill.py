from infra.recovery_drill import migration_sql


def test_drill_dialect_is_not_taken_from_the_application_environment(monkeypatch):
    monkeypatch.setenv("MLCHESS_DATABASE_URL", "sqlite+aiosqlite:///unused.db")
    sql = migration_sql()
    assert "CREATE TABLE worker_jobs" in sql
    assert "ALTER TABLE game_moves ALTER COLUMN actor_id DROP NOT NULL" in sql
