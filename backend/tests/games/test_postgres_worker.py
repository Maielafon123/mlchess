import asyncio
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from backend.app.engine.adapter import EngineError, EngineMove
from backend.app.infra.models import WorkerJob
from backend.app.infra.settings import Settings
from backend.app.main import create_app
from backend.app.workers.runner import FakeEngine, GameplayWorker
from backend.tests.games.test_http_games import create, login
from backend.tests.games.test_postgres_commands import DATABASE_URL

pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="Disposable PostgreSQL URL not configured"
)


def move(http, game, headers):
    response = http.post(
        f"/api/v1/games/{game['id']}/moves",
        json={"uci": "e2e4", "expected_version": 0, "client_move_id": str(uuid4())},
        headers=headers,
    )
    assert response.status_code == 200, response.text


def test_worker_plays_one_durable_reply_and_double_delivery_is_safe(pg_app):
    with TestClient(pg_app) as http:
        headers = login(http)
        game = create(http, headers)
        move(http, game, headers)

        async def exercise():
            worker = GameplayWorker(pg_app.state.database_factory, FakeEngine())
            lease = await worker.claim()
            assert await worker.apply(lease, EngineMove("e7e5")) == "done"
            assert await worker.apply(lease, EngineMove("e7e5")) == "lost"
            assert await worker.run_one() is None

        asyncio.run(exercise())
        snapshot = http.get(f"/api/v1/games/{game['id']}").json()
        assert [m["uci"] for m in snapshot["moves"]] == ["e2e4", "e7e5"]
        assert snapshot["version"] == 2 and snapshot["capabilities"]["can_move"]


def test_old_engine_reply_after_takeback_is_discarded(pg_app):
    with TestClient(pg_app) as http:
        headers = login(http)
        game = create(http, headers)
        move(http, game, headers)
        worker = GameplayWorker(pg_app.state.database_factory, FakeEngine())
        lease = asyncio.run(worker.claim())
        response = http.post(
            f"/api/v1/games/{game['id']}/takeback",
            json={"expected_version": 1, "plies": 1, "client_action_id": str(uuid4())},
            headers=headers,
        )
        assert response.status_code == 200
        assert asyncio.run(worker.apply(lease, EngineMove("e7e5"))) == "stale"
        snapshot = http.get(f"/api/v1/games/{game['id']}").json()
        assert snapshot["moves"] == [] and snapshot["revision"] == 1


def test_expired_lease_is_reclaimed_and_fences_the_old_worker(pg_app):
    with TestClient(pg_app) as http:
        headers = login(http)
        game = create(http, headers)
        move(http, game, headers)

        async def exercise():
            first = GameplayWorker(pg_app.state.database_factory, FakeEngine())
            old = await first.claim()
            async with pg_app.state.database_factory() as session, session.begin():
                job = await session.get(WorkerJob, old.id)
                job.lease_until = datetime.now(timezone.utc) - timedelta(seconds=1)
            restarted = GameplayWorker(pg_app.state.database_factory, FakeEngine())
            new = await restarted.claim()
            assert new.id == old.id and new.token != old.token
            assert await first.apply(old, EngineMove("e7e5")) == "lost"
            assert await restarted.apply(new, EngineMove("e7e5")) == "done"

        asyncio.run(exercise())
        assert http.get(f"/api/v1/games/{game['id']}").json()["ply"] == 2


def test_engine_failure_has_bounded_attempts(pg_app):
    class Unavailable:
        def choose_move(self, *args, **kwargs):
            raise EngineError("simulated unavailable engine")

    with TestClient(pg_app) as http:
        headers = login(http)
        game = create(http, headers)
        move(http, game, headers)

        async def exercise():
            worker = GameplayWorker(
                pg_app.state.database_factory, Unavailable(), max_attempts=1
            )
            assert await worker.run_one() == "failed"
            assert await worker.run_one() is None
            async with pg_app.state.database_factory() as session:
                job = await session.scalar(select(WorkerJob))
                assert job.attempts == 1 and job.failure_code == "ENGINE_FAILURE"

        asyncio.run(exercise())
        assert http.get(f"/api/v1/games/{game['id']}").json()["ply"] == 1


def test_black_human_gets_a_server_owned_opening_move(pg_app):
    with TestClient(pg_app) as http:
        headers = login(http)
        game = create(http, headers, human_color="black")
        worker = GameplayWorker(pg_app.state.database_factory, FakeEngine())
        assert asyncio.run(worker.run_one()) == "done"
        snapshot = http.get(f"/api/v1/games/{game['id']}").json()
        assert snapshot["ply"] == 1 and snapshot["side_to_move"] == "black"
        assert snapshot["capabilities"]["can_move"]


def test_a_crashed_final_attempt_does_not_remain_running_forever(pg_app):
    with TestClient(pg_app) as http:
        headers = login(http)
        game = create(http, headers, human_color="black")

        async def exercise():
            worker = GameplayWorker(
                pg_app.state.database_factory, FakeEngine(), max_attempts=1
            )
            lease = await worker.claim()
            async with pg_app.state.database_factory() as session, session.begin():
                job = await session.get(WorkerJob, lease.id)
                job.lease_until = datetime.now(timezone.utc) - timedelta(seconds=1)
            assert await worker.claim() is None
            async with pg_app.state.database_factory() as session:
                job = await session.get(WorkerJob, lease.id)
                assert job.status == "failed" and job.failure_code == "LEASE_EXHAUSTED"
                assert job.lease_token is None and job.lease_until is None

        asyncio.run(exercise())
        assert http.get(f"/api/v1/games/{game['id']}").json()["ply"] == 0


def test_separate_worker_process_and_restarted_api_share_only_postgres():
    # A generated database is used because a separate process has no test-fixture
    # schema mapping. No existing database is migrated, truncated or dropped.
    database = "test_worker_" + uuid4().hex
    admin = create_async_engine(
        DATABASE_URL, poolclass=NullPool, isolation_level="AUTOCOMMIT"
    )

    async def ddl(statement):
        async with admin.connect() as connection:
            await connection.execute(text(statement))

    asyncio.run(ddl("CREATE DATABASE " + database))
    url = (
        make_url(DATABASE_URL)
        .set(database=database)
        .render_as_string(hide_password=False)
    )
    settings = Settings(
        environment="test",
        public_origin="http://testserver",
        dev_auth_enabled=True,
        database_url=url,
        database_auto_create=False,
    )
    try:
        migrated = subprocess.run(
            [
                sys.executable,
                "-m",
                "alembic",
                "-c",
                "backend/alembic.ini",
                "upgrade",
                "head",
            ],
            env={**os.environ, "MLCHESS_DATABASE_URL": url},
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert migrated.returncode == 0, migrated.stderr
        with TestClient(create_app(settings)) as http:
            headers = login(http)
            game = create(http, headers)
            move(http, game, headers)
            cookies = dict(http.cookies)
        environment = {
            **os.environ,
            "MLCHESS_DATABASE_URL": url,
            "MLCHESS_ENVIRONMENT": "test",
            "MLCHESS_PUBLIC_ORIGIN": "http://testserver",
            "MLCHESS_DEV_AUTH_ENABLED": "false",
        }
        completed = subprocess.run(
            [sys.executable, "-m", "backend.app.workers.runner", "--fake", "--once"],
            env=environment,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert completed.returncode == 0, completed.stderr
        assert '"status": "done"' in completed.stdout
        with TestClient(create_app(settings)) as restarted:
            restarted.cookies.update(cookies)
            snapshot = restarted.get(f"/api/v1/games/{game['id']}").json()
            assert snapshot["ply"] == 2 and snapshot["capabilities"]["can_move"]
    finally:
        assert database.startswith("test_worker_") and len(database) == 44
        asyncio.run(ddl("DROP DATABASE " + database))
        asyncio.run(admin.dispose())
