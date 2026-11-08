"""Learning persists across app restarts and trusts only authenticated server grading."""

import asyncio
from datetime import datetime, timezone
from uuid import UUID
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.app.infra.settings import Settings
from backend.app.infra.models import PuzzleAttemptRow
from backend.app.learning.catalog import seed_test_catalog, load_catalog
from backend.app.main import create_app
from backend.tests.games.test_http_games import login, create
from contracts.validate import validator

ROOT = "/api/v1/learning"


@pytest.fixture
def settings(tmp_path):
    return Settings(
        environment="test",
        public_origin="http://testserver",
        dev_auth_enabled=True,
        database_auto_create=True,
        database_url="sqlite+aiosqlite:///" + (tmp_path / "learning.db").as_posix(),
    )


@pytest.fixture
def http(settings):
    app = create_app(settings)
    with TestClient(app) as client:
        asyncio.run(seed_test_catalog(app.state.database_factory))
        login(client)
        yield client


def command(http, path, payload, *, command_key=None, method="post"):
    return http.request(
        method,
        ROOT + path,
        json={"schema_version": 1, "learning_epoch": 0, **payload},
        headers={
            "Origin": "http://testserver",
            "X-CSRF-Token": http.cookies["mlchess_csrf"],
            "Idempotency-Key": command_key or str(uuid4()),
        },
    )


def attempt(http, uci="d1d8", **overrides):
    return command(
        http,
        "/puzzles/back-rank/attempts",
        {
            "attempt_id": str(uuid4()),
            "uci": uci,
            "session_number": 0,
            "expected_ply": 0,
            **overrides,
        },
    )


def check(schema, value):
    validator(
        "https://mlchess.local/contracts/learning/v1.yaml#/$defs/" + schema
    ).validate(value)


def test_catalog_is_legal_original_and_answers_are_private(http):
    assert len(load_catalog()["puzzles"]) == 4
    lessons = http.get(ROOT + "/lessons?language=en&page_size=2").json()
    check("LessonListV1", lessons)
    assert lessons["total_pages"] == 4
    assert all(row["language"] == "en" for row in lessons["items"])
    puzzles = http.get(ROOT + "/puzzles").json()
    check("PuzzleListV1", puzzles)
    for row in puzzles["items"]:
        assert row["source_url"].endswith("/docs/learning/CURRICULUM.md")
        assert (
            "solution" not in row
            and "hints" not in row
            and "private_solution" not in row
        )
        state = http.get(ROOT + f"/puzzles/{row['id']}/state").json()
        check("PuzzleStateV1", state)
        assert "solution" not in state and state["hints"] == []


def test_hint_replay_is_exact_and_does_not_award_an_attempt(http):
    path = "/puzzles/back-rank/hints"
    payload = {"session_number": 0}
    key = str(uuid4())
    first = command(http, path, payload, command_key=key)
    assert first.status_code == 200, first.text
    assert first.json()["hint_index"] == 1
    assert command(http, path, payload, command_key=key).json() == first.json()
    progress = http.get(ROOT + "/progress").json()
    check("StudentProgressV1", progress)
    assert all(
        s["hints_used"] == 1 and s["attempts"] == 0 and s["due_at"] is None
        for s in progress["skills"]
    )
    assert attempt(http).status_code == 200
    assert all(
        s["hints_used"] == 1 and s["correct"] == 1
        for s in http.get(ROOT + "/progress").json()["skills"]
    )
    for _ in range(5):
        response = command(http, path, payload)
        assert response.status_code == 200
    assert response.json()["hint_index"] == 3 and not response.json()["has_more"]


def test_attempt_deduplication_cas_replay_and_progress(http):
    wrong = attempt(http, "g1f1")
    assert wrong.status_code == 200 and wrong.json()["result"] == "incorrect"
    illegal = attempt(
        http, "d1d7"
    )  # d7 is legal but not the mate: no client-supplied result.
    assert illegal.json()["result"] == "incorrect"
    assert attempt(http, "a1a8").json()["result"] == "illegal"
    stale = attempt(http, expected_ply=1)
    assert stale.status_code == 409
    payload = {
        "attempt_id": "one-verdict",
        "uci": "d1d8",
        "session_number": 0,
        "expected_ply": 0,
    }
    first = command(http, "/puzzles/back-rank/attempts", payload)
    assert first.status_code == 200, first.text
    check("PuzzleAttemptV1", first.json())
    assert first.json()["completed"]
    assert command(http, "/puzzles/back-rank/attempts", payload).json() == first.json()
    assert (
        command(
            http, "/puzzles/back-rank/attempts", {**payload, "uci": "g1f1"}
        ).status_code
        == 409
    )
    assert attempt(http, expected_ply=1).json()["result"] == "completed"
    state = http.get(ROOT + "/puzzles/back-rank/state").json()
    check("PuzzleStateV1", state)
    assert state["solution"][0]["uci"] == "d1d8"
    progress = http.get(ROOT + "/progress").json()
    assert all(s["attempts"] == 4 and s["correct"] == 1 for s in progress["skills"])


def test_underpromotion_mate_and_restart_fences_old_tab(http):
    path = "/puzzles/promotion-finish"
    payload = {
        "attempt_id": "rook-mate",
        "uci": "f7f8r",
        "session_number": 0,
        "expected_ply": 0,
    }
    response = command(http, path + "/attempts", payload)
    assert response.status_code == 200 and response.json()["completed"], response.text
    assert http.get(ROOT + path + "/state").json()["solution"][0]["uci"] == "f7f8r"
    restarted = command(http, path + "/restart", {"session_number": 0})
    assert restarted.status_code == 200
    check("PuzzleStateV1", restarted.json())
    assert (
        restarted.json()["session_number"] == 1 and "solution" not in restarted.json()
    )
    assert (
        command(
            http, path + "/attempts", {**payload, "attempt_id": "stale"}
        ).status_code
        == 409
    )
    assert command(http, path + "/attempts", payload).json() == response.json()


def test_lesson_status_and_puzzle_survive_restart(http, settings):
    first = http.get(ROOT + "/lessons").json()["items"][0]
    path = f"/lessons/{first['id']}/status"
    assert command(http, path, {"status": "completed"}).status_code == 200
    assert command(http, path, {"status": "started"}).json()["status"] == "completed"
    assert attempt(http).json()["completed"]
    with TestClient(create_app(settings)) as restarted:
        restarted.cookies.update(http.cookies)
        assert (
            restarted.get(ROOT + f"/lessons/{first['id']}").json()["status"]
            == "completed"
        )
        assert restarted.get(ROOT + "/puzzles/back-rank/state").json()["completed"]
        assert all(
            s["correct"] == 1
            for s in restarted.get(ROOT + "/progress").json()["skills"]
        )


def test_reset_only_own_learning_and_rejects_pre_reset_commands(http):
    headers = {
        "Origin": "http://testserver",
        "X-CSRF-Token": http.cookies["mlchess_csrf"],
    }
    game = create(http, headers)
    assert attempt(http).json()["completed"]
    key = str(uuid4())
    reset = command(http, "/data", {"confirm": True}, method="delete", command_key=key)
    assert reset.status_code == 204 and reset.content == b""
    assert (
        command(
            http, "/data", {"confirm": True}, method="delete", command_key=key
        ).status_code
        == 204
    )
    assert http.get(ROOT + "/context").json()["learning_epoch"] == 1
    assert http.get(ROOT + "/progress").json()["skills"] == []
    assert http.get(ROOT + "/export").json()["attempts"] == []
    assert attempt(http).status_code == 409
    assert attempt(http, learning_epoch=1).json()["completed"]
    assert http.get("/api/v1/me").status_code == 200
    assert http.get("/api/v1/games/" + game["id"]).status_code == 200


@pytest.mark.parametrize(
    "overrides",
    [
        {"is_correct": True},
        {"expected_ply": True},
        {"session_number": 1.0},
        {"learning_epoch": False},
        {"schema_version": True},
        {"uci": "bad"},
        {"attempt_id": "../x"},
    ],
)
def test_untrusted_attempt_payload_rejected(http, overrides):
    assert attempt(http, **overrides).status_code == 422
    assert http.get(ROOT + "/progress").json()["skills"] == []


@pytest.mark.parametrize("cursor", ["!", "e30", "WzAsbnVsbCwieCJd", "WzAsMSwieCJd"])
def test_malformed_export_cursor_is_422(http, cursor):
    assert http.get(ROOT + "/export", params={"cursor": cursor}).status_code == 422


def test_private_progress_export_and_csrf(http):
    actor = http.get("/api/v1/me").json()["id"]
    assert http.get(ROOT + "/progress", params={"student_id": actor}).status_code == 200
    assert (
        http.get(ROOT + "/progress", params={"student_id": str(uuid4())}).status_code
        == 403
    )
    assert (
        http.get(
            ROOT + "/review-queue", params={"student_id": str(uuid4())}
        ).status_code
        == 403
    )
    assert (
        http.post(
            ROOT + "/puzzles/back-rank/hints",
            json={"schema_version": 1, "learning_epoch": 0, "session_number": 0},
        ).status_code
        == 403
    )
    command(http, "/puzzles/back-rank/hints", {"session_number": 0})
    exported = http.get(ROOT + "/export").json()
    check("LearningExportV1", exported)
    assert exported["next_cursor"] is None and "solution" not in exported["puzzles"][0]
    # Another guest receives a fresh private view, including on the shared puzzle.
    http.cookies.clear()
    login(http, "Other")
    assert http.get(ROOT + "/progress").json()["skills"] == []
    assert http.get(ROOT + "/export").json()["puzzles"] == []


def test_catalog_requires_session_and_durable_storage():
    with TestClient(
        create_app(
            Settings(
                environment="test",
                dev_auth_enabled=True,
                public_origin="http://testserver",
            )
        )
    ) as http:
        assert http.get(ROOT + "/lessons").status_code == 401
        login(http)
        assert http.get(ROOT + "/lessons").status_code == 503


def test_export_paginates_equal_timestamps_and_reset_invalidates_cursor(http):
    actor = UUID(http.get("/api/v1/me").json()["id"])

    async def seed_attempts():
        async with http.app.state.database_factory() as session, session.begin():
            for index in range(102):
                identifier = f"bounded-{index:03}"
                session.add(
                    PuzzleAttemptRow(
                        student_id=actor,
                        attempt_id=identifier,
                        puzzle_id="back-rank",
                        uci="g1f1",
                        session_number=0,
                        request_hash="0" * 64,
                        response={
                            "schema_version": 1,
                            "attempt_id": identifier,
                            "result": "incorrect",
                            "completed": False,
                            "next_ply": 0,
                        },
                        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                    )
                )

    asyncio.run(seed_attempts())
    first = http.get(ROOT + "/export").json()
    check("LearningExportV1", first)
    assert len(first["attempts"]) == 100 and first["next_cursor"]
    second = http.get(ROOT + "/export", params={"cursor": first["next_cursor"]}).json()
    check("LearningExportV1", second)
    assert len(second["attempts"]) == 2 and second["next_cursor"] is None
    assert len({r["attempt_id"] for r in first["attempts"] + second["attempts"]}) == 102
    assert command(http, "/data", {"confirm": True}, method="delete").status_code == 204
    assert (
        http.get(ROOT + "/export", params={"cursor": first["next_cursor"]}).status_code
        == 409
    )


@pytest.mark.parametrize("value", [False, 1, "true", None])
def test_reset_needs_explicit_json_confirmation(http, value):
    assert (
        command(http, "/data", {"confirm": value}, method="delete").status_code == 422
    )
