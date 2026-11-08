import asyncio
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import delete, update
from starlette.websockets import WebSocketDisconnect

from backend.app.games.durable import DurableGameService
from backend.app.infra.models import GameEvent, User
from backend.app.infra.settings import Settings
from backend.app.main import create_app
from backend.tests.games.test_http_games import login, create
from contracts.validate import validator

ORIGIN = {"Origin": "http://testserver"}


@pytest.fixture
def game_http(tmp_path):
    app = create_app(
        Settings(
            environment="test",
            public_origin="http://testserver",
            dev_auth_enabled=True,
            database_auto_create=True,
            database_url="sqlite+aiosqlite:///" + (tmp_path / "stream.db").as_posix(),
        )
    )
    with TestClient(app) as http:
        headers = login(http)
        game = create(http, headers)
        yield http, headers, game


def subscribe(http, game, after=0, headers=ORIGIN):
    return http.websocket_connect(f"/ws/v1/games/{game['id']}", headers=headers)


def send(ws, game, after=0):
    ws.send_json({"type": "subscribe", "game_id": game["id"], "after_seq": after})


def check(frame):
    validator(
        "https://mlchess.local/contracts/game/events.v1.yaml#/$defs/GameEventV1"
    ).validate(frame)


def move(http, headers, game):
    response = http.post(
        f"/api/v1/games/{game['id']}/moves",
        headers=headers,
        json={"client_move_id": str(uuid4()), "expected_version": 0, "uci": "e2e4"},
    )
    assert response.status_code == 200, response.text


def test_atomic_snapshot_live_move_and_retained_replay(game_http):
    http, headers, game = game_http
    with subscribe(http, game) as ws:
        send(ws, game)
        first = ws.receive_json()
        check(first)
        assert first["type"] == "game.snapshot" and first["payload"]["version"] == 0
        move(http, headers, game)
        event = ws.receive_json()
        check(event)
        assert (
            event["type"] == "game.move_committed" and event["seq"] == first["seq"] + 1
        )
        assert event["payload"]["move"]["uci"] == "e2e4"
        undo = http.post(
            f"/api/v1/games/{game['id']}/takeback",
            headers=headers,
            json={"client_action_id": str(uuid4()), "expected_version": 1, "plies": 1},
        )
        assert undo.status_code == 200
        taken_back = ws.receive_json()
        check(taken_back)
        assert taken_back["type"] == "game.takeback_applied"
        assert taken_back["seq"] == event["seq"] + 1
        assert taken_back["payload"]["new_revision"] == 1
    with subscribe(http, game) as resumed:
        send(resumed, game, first["seq"])
        assert resumed.receive_json() == event
        assert resumed.receive_json() == taken_back
    assert http.app.state.ws_connections.actors == {}


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Origin": "https://evil.example"},
        {"Origin": "null"},
        {"Origin": "http://testserver/"},
        {"Origin": "http://testserver", "Host": "evil.example"},
    ],
)
def test_origin_and_host_are_mandatory(game_http, headers):
    http, _, game = game_http
    with pytest.raises(WebSocketDisconnect):
        with subscribe(http, game, headers=headers):
            pytest.fail("Untrusted handshake accepted")


def test_foreign_and_anonymous_cannot_subscribe(game_http):
    http, _, game = game_http
    http.cookies.clear()
    with pytest.raises(WebSocketDisconnect):
        with subscribe(http, game):
            pytest.fail("Anonymous accepted")
    login(http, "Foreign")
    with pytest.raises(WebSocketDisconnect):
        with subscribe(http, game):
            pytest.fail("Non-participant accepted")


@pytest.mark.parametrize("value", [True, -1, 1.5, "1", 9007199254740992])
def test_invalid_cursor_closes_read_only_connection(game_http, value):
    http, _, game = game_http
    with subscribe(http, game) as ws:
        send(ws, game, value)
        with pytest.raises(WebSocketDisconnect) as failure:
            ws.receive_json()
        assert failure.value.code == 1008
    assert http.app.state.ws_connections.actors == {}


def test_ahead_cursor_resync_is_control_then_connection_closes(game_http):
    http, _, game = game_http
    with subscribe(http, game) as ws:
        send(ws, game, 999)
        frame = ws.receive_json()
        check(frame)
        assert frame["type"] == "server.resync_required"
        assert frame["seq"] == frame["payload"]["latest_seq"]
        assert frame["payload"]["reason"] == "cursor_ahead"
        with pytest.raises(WebSocketDisconnect) as failure:
            ws.receive_json()
        assert failure.value.code == 1012


def test_logout_revokes_existing_socket(game_http):
    http, headers, game = game_http
    with subscribe(http, game) as ws:
        send(ws, game)
        ws.receive_json()
        assert http.post("/api/v1/logout", headers=headers).status_code == 204
        with pytest.raises(WebSocketDisconnect) as failure:
            ws.receive_json()
        assert failure.value.code == 4401


def test_deleted_user_loses_an_existing_stream(game_http):
    http, _, game = game_http
    actor = UUID(http.get("/api/v1/me").json()["id"])

    async def delete_disposable_user():
        async with http.app.state.database_factory() as session, session.begin():
            await session.execute(
                update(User)
                .where(User.id == actor)
                .values(deleted_at=datetime.now(timezone.utc))
            )

    with subscribe(http, game) as ws:
        send(ws, game)
        ws.receive_json()
        asyncio.run(delete_disposable_user())
        with pytest.raises(WebSocketDisconnect) as failure:
            ws.receive_json()
        assert failure.value.code == 4401


def test_extra_command_and_oversized_subscription_rejected(game_http):
    http, _, game = game_http
    with subscribe(http, game) as ws:
        send(ws, game)
        ws.receive_json()
        ws.send_json({"type": "move", "uci": "e2e4"})
        with pytest.raises(WebSocketDisconnect) as failure:
            ws.receive_json()
        assert failure.value.code == 1008
    with subscribe(http, game) as ws:
        ws.send_text("x" * 1025)
        with pytest.raises(WebSocketDisconnect) as failure:
            ws.receive_json()
        assert failure.value.code == 1009
    assert http.get(f"/api/v1/games/{game['id']}").json()["version"] == 0


def test_missing_history_never_acknowledges_a_successful_replay(game_http):
    http, headers, game = game_http
    actor = UUID(http.get("/api/v1/me").json()["id"])
    first = asyncio.run(
        http.app.state.event_stream.read(UUID(game["id"]), actor, 0, bootstrap=True)
    )
    move(http, headers, game)

    async def remove_disposable_event():
        async with http.app.state.database_factory() as session, session.begin():
            await session.execute(
                delete(GameEvent).where(
                    GameEvent.game_id == UUID(game["id"]), GameEvent.seq > first.cursor
                )
            )

    asyncio.run(remove_disposable_event())
    with subscribe(http, game) as ws:
        send(ws, game, first.cursor)
        frame = ws.receive_json()
        assert (
            frame["type"] == "server.resync_required"
            and frame["payload"]["reason"] == "replay_unavailable"
        )


def test_private_coach_and_pvp_analysis_references_force_safe_snapshot(game_http):
    http, headers, coach_game = game_http
    actor = UUID(http.get("/api/v1/me").json()["id"])
    response = http.post(
        "/api/v1/games",
        json={"mode": "friend", "time_control": None},
        headers={**headers, "Idempotency-Key": str(uuid4())},
    )
    assert response.status_code == 201
    friend = response.json()

    async def append_reference(game, kind):
        async with http.app.state.database_factory() as session, session.begin():
            row, state, _ = await DurableGameService.load(
                session, UUID(game["id"]), actor, lock=True
            )
            cursor = state.event_seq
            payload = {"analysis_id": str(uuid4()), "revision": 0, "ply": 1}
            if kind == "coach.ready":
                payload["explanation_id"] = str(uuid4())
            DurableGameService.event(
                session,
                row,
                state,
                kind,
                payload,
                await DurableGameService.now(session),
            )
            return cursor

    for game, kind in ((friend, "analysis.ready"), (coach_game, "coach.ready")):
        cursor = asyncio.run(append_reference(game, kind))
        with subscribe(http, game) as ws:
            send(ws, game, cursor)
            frame = ws.receive_json()
            check(frame)
            assert frame["type"] == "server.resync_required"
            assert "analysis_id" not in str(frame) and "explanation_id" not in str(
                frame
            )


def test_capacity_is_released_after_disconnection(game_http):
    from contextlib import ExitStack

    http, _, game = game_http
    with ExitStack() as stack:
        for _ in range(4):
            ws = stack.enter_context(subscribe(http, game))
            send(ws, game)
            ws.receive_json()
        with pytest.raises(WebSocketDisconnect):
            with subscribe(http, game):
                pytest.fail("Per-actor connection limit ignored")
    assert http.app.state.ws_connections.actors == {}
    with subscribe(http, game) as ws:
        send(ws, game)
        assert ws.receive_json()["type"] == "game.snapshot"


def test_duplicate_fields_and_query_credentials_are_rejected(game_http):
    http, _, game = game_http
    with subscribe(http, game) as ws:
        ws.send_text(
            '{"type":"subscribe","game_id":"'
            + game["id"]
            + '","after_seq":0,"after_seq":1}'
        )
        with pytest.raises(WebSocketDisconnect) as failure:
            ws.receive_json()
        assert failure.value.code == 1008
    with pytest.raises(WebSocketDisconnect):
        with http.websocket_connect(
            f"/ws/v1/games/{game['id']}?token=untrusted", headers=ORIGIN
        ):
            pytest.fail("Query credential accepted")


def test_verified_ready_references_deliver_to_requester_and_undo_fences_old_revision(
    game_http,
):
    from backend.app.coach.worker import CoachWorker
    from backend.tests.coach.test_durable_coach import setup_analysis, body, post

    http, headers, _ = game_http
    game, analysis = setup_analysis(http.app, http, headers)
    accepted = post(http, game, body(game, analysis), headers)
    assert accepted.status_code == 202
    assert asyncio.run(CoachWorker(http.app.state.database_factory).run_one()) == "done"
    with subscribe(http, game) as ws:
        send(ws, game, 1)
        frames = [ws.receive_json() for _ in range(3)]
        assert [frame["type"] for frame in frames] == [
            "game.move_committed",
            "analysis.ready",
            "coach.ready",
        ]
        assert frames[2]["payload"]["explanation_id"] == accepted.json()["job_id"]
        for frame in frames:
            check(frame)
    undo = http.post(
        f"/api/v1/games/{game['id']}/takeback",
        headers=headers,
        json={"client_action_id": str(uuid4()), "expected_version": 1, "plies": 1},
    )
    assert undo.status_code == 200
    with subscribe(http, game) as ws:
        send(ws, game, 1)
        frame = ws.receive_json()
        assert frame["type"] == "server.resync_required"
        assert "analysis_id" not in str(frame)
