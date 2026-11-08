import asyncio
import os
import subprocess
import sys

import asyncpg
import pytest

from infra.container_probe import database


def test_worker_probe_uses_bounded_driver_and_always_closes(monkeypatch):
    calls = []

    class Connection:
        async def fetchval(self, sql):
            calls.append(sql)
            raise RuntimeError("private failure")

        async def close(self, **kwargs):
            calls.append(kwargs)

    async def connect(url, **kwargs):
        assert url == "postgresql://user:disposable@127.0.0.1/db"
        assert kwargs == {"timeout": 2, "command_timeout": 2}
        return Connection()

    monkeypatch.setenv(
        "MLCHESS_DATABASE_URL", "postgresql+asyncpg://user:disposable@127.0.0.1/db"
    )
    monkeypatch.setattr(asyncpg, "connect", connect)
    with pytest.raises(RuntimeError):
        asyncio.run(database())
    assert calls == ["SELECT id FROM worker_jobs LIMIT 1", {"timeout": 1}]


def test_importing_probe_does_not_import_sqlalchemy_or_application():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import infra.container_probe; assert 'sqlalchemy' not in sys.modules; assert 'backend.app.main' not in sys.modules",
        ],
        capture_output=True,
        timeout=10,
    )
    assert result.returncode == 0


def test_probe_failure_does_not_print_connection_secret():
    result = subprocess.run(
        [sys.executable, "-m", "infra.container_probe", "worker"],
        env={**os.environ, "MLCHESS_DATABASE_URL": "invalid://private-secret"},
        capture_output=True,
        timeout=10,
    )
    assert result.returncode == 1
    assert result.stdout == b"" and result.stderr == b""
