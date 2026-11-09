"""Durable deadlines use the same transition as late commands, even after restart."""

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select

from backend.app.games.domain import GameDomain, Mode
from backend.app.games.durable import DurableGameService, encode_domain
from backend.app.infra.models import Game, GameEvent, GameState, GameMove, OutboxEvent
from backend.app.infra.settings import Settings
from backend.app.main import create_app
from backend.app.workers.clock import ClockScheduler
from backend.tests.games.test_http_games import create, login
from backend.tests.games.test_guest_invitations import guest, command

START = datetime(2026, 1, 1, tzinfo=timezone.utc)
TIMED = {"initial_ms": 1000, "increment_ms": 250}


@pytest.fixture
def timed(tmp_path, monkeypatch):
    settings = Settings(
        environment="test",
        public_origin="http://testserver",
        dev_auth_enabled=True,
        invitation_secret="x" * 43,
        database_auto_create=True,
        database_url="sqlite+aiosqlite:///" + (tmp_path / "clocks.db").as_posix(),
    )
    time = [START]

    async def now(_session):
        return time[0]

    monkeypatch.setattr(DurableGameService, "now", staticmethod(now))
    with TestClient(create_app(settings)) as http:
        headers = login(http)
        yield http, headers, time, settings


def tick(http):
    return asyncio.run(ClockScheduler(http.app.state.database_factory).run_one())


def path(game):
    return f"/api/v1/games/{game['id']}"


def move(http, headers, game):
    return http.post(
        path(game) + "/moves",
        headers=headers,
        json={"client_move_id": str(uuid4()), "expected_version": 0, "uci": "e2e4"},
    )


def test_idle_timeout_at_exact_deadline_after_restart_commits_once(timed):
    http, headers, time, settings = timed
    game = create(http, headers, time_control=TIMED)
    time[0] = START + timedelta(microseconds=999999)
    assert tick(http) is None
    assert http.get(path(game)).json()["clock"]["white_remaining_ms"] == 1
    with TestClient(create_app(settings)) as restarted:
        restarted.cookies.update(http.cookies)
        time[0] = START + timedelta(seconds=1)
        assert tick(restarted) == "expired"
        assert tick(restarted) is None
        finished = restarted.get(path(game)).json()
        assert (
            finished["status"],
            finished["version"],
            finished["result"],
            finished["termination"],
        ) == ("finished", 1, "black", "timeout")
        assert finished["clock"]["white_remaining_ms"] == 0
        assert finished["clock"]["running_side"] is None
        assert move(restarted, headers, game).status_code == 409

        async def verify():
            async with restarted.app.state.database_factory() as session:
                events = list(
                    await session.scalars(
                        select(GameEvent)
                        .where(GameEvent.game_id == UUID(game["id"]))
                        .order_by(GameEvent.seq)
                    )
                )
                assert [
                    event.payload["payload"]["termination"] for event in events
                ] == [None, "timeout"]
                assert await session.get(OutboxEvent, events[-1].id) is not None
                assert not list(await session.scalars(select(GameMove)))

        asyncio.run(verify())


def test_backward_sample_never_refunds_time_and_move_reindexes(timed):
    http, headers, time, _ = timed
    game = create(http, headers, time_control=TIMED)
    time[0] = START + timedelta(milliseconds=900)
    observed = http.get(path(game)).json()["clock"]
    assert observed["white_remaining_ms"] == 100
    time[0] = START + timedelta(milliseconds=500)
    assert http.get(path(game)).json()["clock"] == observed
    time[0] = START + timedelta(milliseconds=950)
    accepted = move(http, headers, game)
    assert accepted.status_code == 200, accepted.text
    clock = accepted.json()["snapshot"]["clock"]
    assert clock["white_remaining_ms"] == 300 and clock["running_side"] == "black"
    time[0] = START + timedelta(milliseconds=1001)
    assert tick(http) is None
    assert http.get(path(game)).json()["clock"]["black_remaining_ms"] == 949
    time[0] = START + timedelta(milliseconds=1950)
    assert tick(http) == "expired"
    assert http.get(path(game)).json()["result"] == "white"


def test_friend_clock_stays_paused_until_second_seat(timed):
    http, headers, time, _ = timed
    response = http.post(
        "/api/v1/games",
        headers=command(headers),
        json={"mode": "friend", "time_control": TIMED},
    )
    assert response.status_code == 201
    game = response.json()
    invitation = http.post(
        "/api/v1/invitations", headers=command(headers), json={"game_id": game["id"]}
    ).json()
    token = invitation["invite_url"].split("#token=", 1)[1]
    time[0] = START + timedelta(hours=1)
    assert tick(http) is None
    assert http.get(path(game)).json()["clock"]["running_side"] is None
    with TestClient(http.app) as other:
        second = guest(other)
        accepted = other.post(
            f"/api/v1/invitations/{invitation['invite_id']}/accept",
            headers=command(second),
            json={"token": token},
        )
        assert accepted.status_code == 200, accepted.text
        assert http.get(path(game)).json()["clock"]["white_remaining_ms"] == 1000
        time[0] += timedelta(seconds=1)
        assert tick(http) == "expired"
        assert (
            http.get(path(game)).json()["result"]
            == other.get(path(game)).json()["result"]
            == "black"
        )


def test_corrupt_projection_cannot_award_a_win_or_block_other_games(timed):
    http, headers, time, _ = timed
    bad = create(http, headers, time_control=TIMED)
    good = create(http, headers, time_control={"initial_ms": 2000, "increment_ms": 0})

    async def corrupt_disposable_clock():
        async with http.app.state.database_factory() as session, session.begin():
            state = await session.get(GameState, UUID(bad["id"]))
            state.clock = {**state.clock, "running_side": False}

    asyncio.run(corrupt_disposable_clock())
    time[0] += timedelta(seconds=3)
    assert tick(http) == "quarantined"
    assert tick(http) == "expired"
    assert tick(http) is None
    assert http.get(path(good)).json()["result"] == "black"

    async def verify():
        async with http.app.state.database_factory() as session:
            row = await session.get(Game, UUID(bad["id"]))
            assert (
                row.status == "active"
                and row.result is None
                and row.clock_deadline_at is None
            )

    asyncio.run(verify())


def test_timeout_is_draw_when_opponent_cannot_mate(timed):
    http, headers, time, _ = timed
    game = create(http, headers, time_control=TIMED)
    position = GameDomain.start(Mode.COACH, initial_fen="7k/8/8/8/8/8/8/KR6 w - - 0 1")

    async def restore_disposable_position():
        async with http.app.state.database_factory() as session, session.begin():
            row = await session.get(Game, UUID(game["id"]))
            state = await session.get(GameState, row.id)
            row.fen, state.domain = position.fen, encode_domain(position)

    asyncio.run(restore_disposable_position())
    time[0] += timedelta(seconds=1)
    assert tick(http) == "expired"
    finished = http.get(path(game)).json()
    assert finished["result"] == "draw" and finished["termination"] == "timeout"
