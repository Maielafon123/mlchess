from infra.compose_diagnostics import redact


def test_connection_passwords_and_env_secrets_never_reach_logs():
    value = "postgresql+asyncpg://mlchess:unlisted-password@127.0.0.1:55432/mlchess example-secret"
    safe = redact(value, ["example-secret"])
    assert "unlisted-password" not in safe
    assert "example-secret" not in safe
    assert "127.0.0.1:55432" in safe
