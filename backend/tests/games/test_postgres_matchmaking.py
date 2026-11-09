"""Exercise real PostgreSQL queue and settlement locks."""

import asyncio
from datetime import timedelta
import os
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select

from backend.app.games.durable import DurableGameService, iso
from backend.app.infra.models import (
    Game,
    GameEvent,
    GameMove,
    GameState,
    MatchTicketRow,
    OutboxEvent,
    Rating,
    RatingSettlementRow,
)
from backend.app.infra.problems import PublicProblem
from backend.app.workers.clock import ClockScheduler
from backend.tests.games.test_http_games import login
from backend.tests.matchmaking.test_durable_rated import RAPID

pytestmark = pytest.mark.skipif(
    not os.environ.get("MLCHESS_TEST_DATABASE_URL"),
    reason="Disposable PostgreSQL URL not configured",
)


def actors(app):
    with TestClient(app) as http:
        result = []
        for name in ("First rated player", "Second rated player"):
            login(http, name)
            result.append(UUID(http.get("/api/v1/me").json()["id"]))
        assert result[0] != result[1]
        return result


def test_parallel_joins_with_retry_and_competing_timeout_settle_once(pg_app):
    first, second = actors(pg_app)
    match = pg_app.state.matchmaking_service
    games = pg_app.state.game_service
    factory = pg_app.state.database_factory

    async def scenario():
        key = uuid4()
        one, two, retry = await asyncio.gather(
            match.join(first, uuid4(), RAPID),
            match.join(second, key, RAPID),
            match.join(second, key, RAPID),
        )
        assert two == retry
        t1, t2 = await asyncio.gather(
            match.get(first, UUID(one["ticket_id"])),
            match.get(second, UUID(two["ticket_id"])),
        )
        assert t1["status"] == t2["status"] == "matched"
        assert t1["game_id"] == t2["game_id"]
        game_id = UUID(t1["game_id"])
        detail = await match.rated_game(first, game_id)
        white = first if detail["side"] == "white" else second
        black = second if white == first else first

        async with factory() as session, session.begin():
            assert len(list(await session.scalars(select(Game)))) == 1
            assert len(list(await session.scalars(select(MatchTicketRow)))) == 2
            row = await session.get(Game, game_id)
            state = await session.get(GameState, game_id)
            now = await DurableGameService.now(session)
            row.clock_deadline_at = now - timedelta(seconds=1)
            state.clock = {
                **state.clock,
                "anchor": iso(now - timedelta(minutes=11)),
            }

        async def late_move():
            with pytest.raises(PublicProblem) as exc:
                await games.command(
                    game_id,
                    white,
                    uuid4(),
                    "move",
                    {
                        "client_move_id": str(uuid4()),
                        "expected_version": 0,
                        "uci": "e2e4",
                    },
                )
            assert exc.value.status == 409

        results = await asyncio.gather(
            ClockScheduler(factory).run_one(),
            ClockScheduler(factory).run_one(),
            late_move(),
        )
        assert results.count("expired") <= 1
        async with factory() as session:
            game = await session.get(Game, game_id)
            assert (game.status, game.version, game.result) == ("finished", 1, "black")
            assert game.clock_deadline_at is None
            settlement = await session.get(RatingSettlementRow, game_id)
            assert (settlement.white_id, settlement.black_id) == (white, black)
            assert (settlement.white_after, settlement.black_after) == (1184, 1216)
            ratings = {
                r.user_id: (r.rating, r.games_count)
                for r in await session.scalars(select(Rating))
            }
            assert ratings == {white: (1184, 1), black: (1216, 1)}
            assert not list(await session.scalars(select(GameMove)))
            events = list(
                await session.scalars(select(GameEvent).order_by(GameEvent.seq))
            )
            assert len(events) == 2
            assert events[-1].payload["payload"]["termination"] == "timeout"
            assert await session.get(OutboxEvent, events[-1].id) is not None

    asyncio.run(scenario())


def test_cancel_racing_pair_leaves_either_two_seats_or_no_game(pg_app):
    first, second = actors(pg_app)
    match = pg_app.state.matchmaking_service

    async def scenario():
        one = await match.join(first, uuid4(), RAPID)
        ticket_id = UUID(one["ticket_id"])
        cancel_key = uuid4()

        async def cancel():
            try:
                return await match.cancel(first, cancel_key, ticket_id)
            except PublicProblem as problem:
                assert problem.status == 409
                return None

        cancelled, two = await asyncio.gather(
            cancel(), match.join(second, uuid4(), RAPID)
        )
        latest = await match.get(first, ticket_id)
        async with pg_app.state.database_factory() as session:
            games = list(await session.scalars(select(Game)))
        if cancelled:
            assert cancelled == latest and latest["status"] == "cancelled"
            assert await cancel() == cancelled
            assert two["status"] == "searching" and not games
        else:
            assert latest["status"] == two["status"] == "matched"
            assert len(games) == 1
            assert latest["game_id"] == two["game_id"] == str(games[0].id)

    asyncio.run(scenario())
