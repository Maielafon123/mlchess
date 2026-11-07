"""Run with MLCHESS_TEST_DATABASE_URL against a disposable PostgreSQL server.

Each test owns a random schema; no existing application tables are changed.
"""

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool
from sqlalchemy.schema import CreateSchema, DropSchema

from backend.app.infra.db import create_schema
from backend.app.infra.models import (
    CommandReceipt,
    Game,
    GameEvent,
    GameMove,
    GamePlayer,
    OutboxEvent,
)
from backend.app.infra.settings import Settings
from backend.app.main import create_app
from backend.tests.games.test_http_games import CREATE, create, login

DATABASE_URL = os.environ.get("MLCHESS_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="Disposable PostgreSQL URL not configured"
)


@pytest.fixture
def pg_app():
    if not DATABASE_URL.startswith("postgresql+asyncpg://"):
        pytest.fail("Integration tests require PostgreSQL/asyncpg")
    schema = "test_a008_" + uuid4().hex
    base = create_async_engine(DATABASE_URL, poolclass=NullPool)
    engine = base.execution_options(schema_translate_map={None: schema})

    async def setup():
        async with base.begin() as connection:
            await connection.execute(CreateSchema(schema))
        await create_schema(engine)

    async def cleanup():
        assert schema.startswith("test_a008_") and len(schema) == 42
        async with base.begin() as connection:
            await connection.execute(DropSchema(schema, cascade=True))
        await base.dispose()

    asyncio.run(setup())
    app = create_app(
        Settings(
            environment="test", public_origin="http://testserver", dev_auth_enabled=True
        ),
        database_engine=engine,
    )
    try:
        yield app
    finally:
        asyncio.run(cleanup())


def rows(app):
    async def count():
        async with app.state.database_factory() as session:
            return {
                model.__tablename__: await session.scalar(
                    select(func.count()).select_from(model)
                )
                for model in (Game, GameMove, GameEvent, OutboxEvent, CommandReceipt)
            }

    return asyncio.run(count())


def test_postgres_two_requests_one_version_and_atomic_receipts(pg_app):
    with TestClient(pg_app) as http:
        headers = login(http)
        game = create(http, headers)
        commands = [
            {"client_move_id": str(uuid4()), "expected_version": 0, "uci": uci}
            for uci in ("e2e4", "d2d4")
        ]

        def send(command):
            return http.post(
                f"/api/v1/games/{game['id']}/moves", json=command, headers=headers
            )

        with ThreadPoolExecutor(2) as pool:
            responses = list(pool.map(send, commands))
        assert sorted(r.status_code for r in responses) == [200, 409], [
            r.text for r in responses
        ]
        accepted = next(r for r in responses if r.status_code == 200)
        command = commands[responses.index(accepted)]
        assert send(command).json() == accepted.json()
        assert rows(pg_app) == {
            "games": 1,
            "game_moves": 1,
            "game_events": 2,
            "outbox_events": 3,
            "command_receipts": 2,
        }


def test_postgres_duplicate_create_from_two_app_instances(pg_app):
    replica = create_app(
        pg_app.state.settings, database_engine=pg_app.state.database_factory.kw["bind"]
    )
    with TestClient(pg_app) as first, TestClient(replica) as second:
        headers = login(first)
        second.cookies.update(dict(first.cookies))
        headers["Idempotency-Key"] = str(uuid4())
        with ThreadPoolExecutor(2) as pool:
            requests = [
                pool.submit(http.post, "/api/v1/games", json=CREATE, headers=headers)
                for http in (first, second)
            ]
            responses = [future.result() for future in requests]
        assert [r.status_code for r in responses] == [201, 201], [
            r.text for r in responses
        ]
        assert responses[0].json() == responses[1].json()
        assert rows(pg_app)["games"] == 1


def test_postgres_failed_outbox_does_not_commit_a_move(pg_app, monkeypatch):
    with TestClient(pg_app) as http:
        headers = login(http)
        game = create(http, headers)
        before = rows(pg_app)

        def fail(*args, **kwargs):
            raise RuntimeError("simulated durable event failure")

        monkeypatch.setattr(pg_app.state.game_service, "event", fail)
        response = http.post(
            f"/api/v1/games/{game['id']}/moves",
            json={"client_move_id": str(uuid4()), "uci": "e2e4", "expected_version": 0},
            headers=headers,
        )
        assert response.status_code == 500
        assert rows(pg_app) == before
        assert http.get(f"/api/v1/games/{game['id']}").json()["version"] == 0


def test_postgres_server_timeout_commits_even_when_move_is_rejected(pg_app):
    with TestClient(pg_app) as http:
        headers = login(http)
        game = create(
            http, headers, time_control={"initial_ms": 1000, "increment_ms": 0}
        )
        now = datetime.fromisoformat(
            game["clock"]["server_now"].replace("Z", "+00:00")
        ) + timedelta(seconds=2)

        async def clock(session):
            return now

        pg_app.state.game_service.now = clock
        response = http.post(
            f"/api/v1/games/{game['id']}/moves",
            json={"client_move_id": str(uuid4()), "uci": "e2e4", "expected_version": 0},
            headers=headers,
        )
        assert response.status_code == 409, response.text
        snapshot = http.get(f"/api/v1/games/{game['id']}").json()
        assert (snapshot["status"], snapshot["result"], snapshot["termination"]) == (
            "finished",
            "black",
            "timeout",
        )
        assert snapshot["moves"] == [] and snapshot["clock"]["running_side"] is None


def test_postgres_full_history_claim_and_terminal_commands(pg_app):
    with TestClient(pg_app) as alice, TestClient(pg_app) as bob:
        ah, bh = login(alice), login(bob, "Bob")
        response = alice.post(
            "/api/v1/games",
            json={"mode": "friend", "time_control": None},
            headers={**ah, "Idempotency-Key": str(uuid4())},
        )
        assert response.status_code == 201, response.text
        game_id = UUID(response.json()["id"])
        bob_id = UUID(bob.get("/api/v1/me").json()["id"])

        async def fixture_join():
            # Trusted fixture for A-018's future invitation acceptance transaction.
            async with pg_app.state.database_factory() as session, session.begin():
                game = await session.get(Game, game_id)
                game.status = "active"
                session.add(
                    GamePlayer(
                        game_id=game_id,
                        side="black",
                        kind="human",
                        user_id=bob_id,
                        joined_at=datetime.now(timezone.utc),
                    )
                )

        asyncio.run(fixture_join())
        moves = ["g1f3", "g8f6", "f3g1", "f6g8"] * 2
        for version, uci in enumerate(moves):
            http, headers = (alice, ah) if version % 2 == 0 else (bob, bh)
            result = http.post(
                f"/api/v1/games/{game_id}/moves",
                json={
                    "uci": uci,
                    "expected_version": version,
                    "client_move_id": str(uuid4()),
                },
                headers=headers,
            )
            assert result.status_code == 200, result.text
        # A bare FEN cannot establish repetitions. Reconstruct the persisted line.
        claim = alice.post(
            f"/api/v1/games/{game_id}/claim-draw",
            json={"expected_version": 8},
            headers={**ah, "Idempotency-Key": str(uuid4())},
        )
        assert claim.status_code == 200, claim.text
        assert (
            claim.json()["termination"] == "threefold_claim"
            and claim.json()["result"] == "draw"
        )
