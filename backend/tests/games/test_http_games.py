from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.app.infra.settings import Settings
from backend.app.main import create_app
from contracts.validate import check_snapshot_fixture, validator


def login(http, name="Alice"):
    response = http.post(
        "/api/v1/auth/dev-login",
        json={"display_name": name},
        headers={"Origin": "http://testserver"},
    )
    assert response.status_code == 200, response.text
    return {"Origin": "http://testserver", "X-CSRF-Token": http.cookies["mlchess_csrf"]}


@pytest.fixture
def settings(tmp_path):
    return Settings(
        environment="test",
        public_origin="http://testserver",
        dev_auth_enabled=True,
        database_url="sqlite+aiosqlite:///" + (tmp_path / "games.db").as_posix(),
        database_auto_create=True,
    )


CREATE = {
    "mode": "coach",
    "time_control": None,
    "human_color": "white",
    "ai_profile": "casual",
}


def create(http, headers, **overrides):
    response = http.post(
        "/api/v1/games",
        json={**CREATE, **overrides},
        headers={**headers, "Idempotency-Key": str(uuid4())},
    )
    assert response.status_code == 201, response.text
    validator(
        "https://mlchess.local/contracts/game/v1.yaml#/$defs/GameSnapshotV1"
    ).validate(response.json())
    check_snapshot_fixture(response.json())
    return response.json()


def test_durable_http_move_replay_takeback_and_restart(settings):
    with TestClient(create_app(settings)) as http:
        headers = login(http)
        game = create(http, headers)
        game_id = game["id"]
        move = {"client_move_id": str(uuid4()), "expected_version": 0, "uci": "e2e4"}
        accepted = http.post(
            f"/api/v1/games/{game_id}/moves", json=move, headers=headers
        )
        assert accepted.status_code == 200, accepted.text
        validator(
            "https://mlchess.local/contracts/game/v1.yaml#/$defs/MoveAcceptedV1"
        ).validate(accepted.json())
        check_snapshot_fixture(accepted.json()["snapshot"])
        assert accepted.json()["snapshot"]["moves"][0]["san"] == "e4"
        assert (
            http.post(
                f"/api/v1/games/{game_id}/moves", json=move, headers=headers
            ).json()
            == accepted.json()
        )
        assert (
            http.post(
                f"/api/v1/games/{game_id}/moves",
                json={**move, "uci": "d2d4"},
                headers=headers,
            ).status_code
            == 409
        )
        undo = http.post(
            f"/api/v1/games/{game_id}/takeback",
            json={"client_action_id": str(uuid4()), "expected_version": 1, "plies": 1},
            headers=headers,
        )
        assert undo.status_code == 200, undo.text
        assert undo.json()["revision"] == 1
        assert undo.json()["moves"] == []
        cookies = dict(http.cookies)
    with TestClient(create_app(settings)) as restarted:
        restarted.cookies.update(cookies)
        assert restarted.get("/api/v1/me").status_code == 200
        snapshot = restarted.get(f"/api/v1/games/{game_id}").json()
        assert snapshot["version"] == 2 and snapshot["revision"] == 1
        assert (
            restarted.post(
                f"/api/v1/games/{game_id}/moves", json=move, headers=headers
            ).json()
            == accepted.json()
        )


def test_create_idempotency_and_request_boundaries(settings):
    with TestClient(create_app(settings)) as http:
        headers = {**login(http), "Idempotency-Key": str(uuid4())}
        first = http.post("/api/v1/games", json=CREATE, headers=headers)
        assert first.status_code == 201, first.text
        assert (
            http.post("/api/v1/games", json=CREATE, headers=headers).json()
            == first.json()
        )
        assert (
            http.post(
                "/api/v1/games", json={**CREATE, "mode": "ai"}, headers=headers
            ).status_code
            == 409
        )
        assert (
            http.post(
                "/api/v1/games", json=CREATE, headers={"Origin": "http://testserver"}
            ).status_code
            == 403
        )
        for bad in (
            {"mode": "ai"},
            {**CREATE, "fen": "injected"},
            {**CREATE, "time_control": {"initial_ms": True, "increment_ms": 0}},
        ):
            assert (
                http.post("/api/v1/games", json=bad, headers=headers).status_code == 422
            )


def test_move_id_scope_is_per_game_and_resign_is_idempotent(settings):
    with TestClient(create_app(settings)) as http:
        headers = login(http)
        first, second = create(http, headers), create(http, headers)
        command = {"client_move_id": str(uuid4()), "expected_version": 0, "uci": "e2e4"}
        for game in (first, second):
            response = http.post(
                f"/api/v1/games/{game['id']}/moves", json=command, headers=headers
            )
            assert response.status_code == 200, response.text
        action_headers = {**headers, "Idempotency-Key": str(uuid4())}
        url = f"/api/v1/games/{first['id']}/resign"
        resigned = http.post(url, json={"expected_version": 1}, headers=action_headers)
        assert resigned.status_code == 200, resigned.text
        assert resigned.json()["result"] == "black"
        assert (
            http.post(url, json={"expected_version": 1}, headers=action_headers).json()
            == resigned.json()
        )


def test_foreign_actor_is_denied_and_friend_cannot_takeback(settings):
    with TestClient(create_app(settings)) as http:
        alice_headers = login(http)
        friend = http.post(
            "/api/v1/games",
            json={"mode": "friend", "time_control": None},
            headers={**alice_headers, "Idempotency-Key": str(uuid4())},
        )
        assert friend.status_code == 201, friend.text
        game_id = friend.json()["id"]
        assert friend.json()["status"] == "waiting"
        assert (
            http.post(
                f"/api/v1/games/{game_id}/takeback",
                json={
                    "expected_version": 0,
                    "plies": 1,
                    "client_action_id": str(uuid4()),
                },
                headers=alice_headers,
            ).status_code
            == 403
        )
        bob_headers = login(http, "Bob")
        assert http.get(f"/api/v1/games/{game_id}").status_code == 403
        assert (
            http.post(
                f"/api/v1/games/{game_id}/moves",
                json={
                    "uci": "e2e4",
                    "expected_version": 0,
                    "client_move_id": str(uuid4()),
                },
                headers=bob_headers,
            ).status_code
            == 403
        )
