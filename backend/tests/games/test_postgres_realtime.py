"""The snapshot/replay boundary remains coherent while a PostgreSQL writer waits."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
import os
import re
import threading
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event

from backend.tests.games.test_http_games import login, create

pytestmark = pytest.mark.skipif(
    not os.environ.get("MLCHESS_TEST_DATABASE_URL"),
    reason="Disposable PostgreSQL URL not configured",
)


def test_snapshot_cursor_and_racing_live_commit_have_no_gap(pg_app):
    with TestClient(pg_app) as http:
        headers = login(http)
        game = create(http, headers)
        actor = UUID(http.get("/api/v1/me").json()["id"])
        game_id = UUID(game["id"])
        engine = pg_app.state.database_factory.kw["bind"].sync_engine
        local = threading.local()
        captured, resume, writer_reached, writer_done = [
            threading.Event() for _ in range(4)
        ]

        def game_query(statement):
            return re.search(r"\bFROM (?:\w+\.)?games\b", statement, re.I) is not None

        def after_read(_conn, _cursor, statement, _params, _context, _many):
            if (
                getattr(local, "reader", False)
                and game_query(statement)
                and not captured.is_set()
            ):
                captured.set()
                assert resume.wait(5), "Snapshot reader gate timed out"

        def before_write(_conn, _cursor, statement, _params, _context, _many):
            if not getattr(local, "reader", False) and game_query(statement):
                writer_reached.set()

        def read():
            local.reader = True
            return asyncio.run(
                pg_app.state.event_stream.read(game_id, actor, 0, bootstrap=True)
            )

        def write():
            try:
                return asyncio.run(
                    pg_app.state.game_service.command(
                        game_id,
                        actor,
                        uuid4(),
                        "move",
                        {
                            "client_move_id": str(uuid4()),
                            "expected_version": 0,
                            "uci": "e2e4",
                        },
                    )
                )
            finally:
                writer_done.set()

        event.listen(engine, "after_cursor_execute", after_read)
        event.listen(engine, "before_cursor_execute", before_write)
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                reader = pool.submit(read)
                assert captured.wait(5)
                writer = pool.submit(write)
                assert writer_reached.wait(5)
                writer_done.wait(0.5)
                resume.set()
                snapshot = reader.result(timeout=5)
                assert writer.result(timeout=5)["snapshot"]["version"] == 1
        finally:
            resume.set()
            event.remove(engine, "after_cursor_execute", after_read)
            event.remove(engine, "before_cursor_execute", before_write)
        assert snapshot.frames[0]["payload"]["version"] == 0
        live = asyncio.run(
            pg_app.state.event_stream.read(game_id, actor, snapshot.cursor)
        )
        assert not live.resync
        assert live.frames[0]["seq"] == snapshot.cursor + 1
        assert live.frames[0]["type"] == "game.move_committed"
        assert live.frames[0]["payload"]["move"]["uci"] == "e2e4"
