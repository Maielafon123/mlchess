"""Real PostgreSQL row locks fence timeout, late moves and competing schedulers."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import os
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select

from backend.app.games.durable import DurableGameService, iso
from backend.app.infra.models import Game, GameEvent, GameMove, GameState, OutboxEvent
from backend.app.infra.problems import PublicProblem
from backend.app.workers.clock import ClockScheduler
from backend.tests.games.test_http_games import create, login

pytestmark = pytest.mark.skipif(
    not os.environ.get("MLCHESS_TEST_DATABASE_URL"),
    reason="Disposable PostgreSQL URL not configured",
)


def test_two_schedulers_and_late_http_move_settle_timeout_once(pg_app):
    with TestClient(pg_app) as http:
        headers = login(http)
        game = create(
            http, headers, time_control={"initial_ms": 1000, "increment_ms": 0}
        )
        game_id, actor = UUID(game["id"]), UUID(http.get("/api/v1/me").json()["id"])
        factory = pg_app.state.database_factory

        async def make_disposable_clock_overdue():
            async with factory() as session, session.begin():
                row = await session.get(Game, game_id)
                state = await session.get(GameState, game_id)
                now = await DurableGameService.now(session)
                row.clock_deadline_at = now - timedelta(seconds=1)
                state.clock = {**state.clock, "anchor": iso(now - timedelta(seconds=2))}

        asyncio.run(make_disposable_clock_overdue())

        def scheduler():
            return asyncio.run(ClockScheduler(factory).run_one())

        def late_move():
            with pytest.raises(PublicProblem) as exc:
                asyncio.run(
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
            assert exc.value.status == 409

        with ThreadPoolExecutor(max_workers=3) as pool:
            results = [pool.submit(task) for task in (scheduler, scheduler, late_move)]
            assert [result.result() for result in results].count("expired") <= 1

        async def verify():
            async with factory() as session:
                row = await session.get(Game, game_id)
                assert (
                    row.status == "finished"
                    and row.version == 1
                    and row.clock_deadline_at is None
                )
                events = list(
                    await session.scalars(
                        select(GameEvent)
                        .where(GameEvent.game_id == game_id)
                        .order_by(GameEvent.seq)
                    )
                )
                assert (
                    len(events) == 2
                    and events[-1].payload["payload"]["termination"] == "timeout"
                )
                assert await session.get(OutboxEvent, events[-1].id) is not None
                assert not list(
                    await session.scalars(
                        select(GameMove).where(GameMove.game_id == game_id)
                    )
                )

        asyncio.run(verify())
