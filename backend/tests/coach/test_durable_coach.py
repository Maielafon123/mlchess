import asyncio
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.app.analysis.worker import AnalysisWorker
from backend.app.coach.providers.rules import RulesCoachProvider
from backend.app.coach.execution import execute
from backend.app.coach.service import CoachJob
from backend.app.coach.worker import CoachWorker
from backend.app.infra.models import GameEvent
from backend.app.main import create_app
from backend.tests.analysis.helpers import AnalysisEngine, METADATA, move, submit
from backend.tests.games.test_http_games import create, login
from contracts.validate import validator


def body(game, analysis):
    return {
        "schema_version": 1,
        "game_id": game["id"],
        "analysis_id": analysis["id"],
        "revision": 0,
        "ply": 1,
        "language": "ru",
        "level": "observation",
    }


def post(http, game, payload, headers, *, key=None):
    return http.post(
        f"/api/v1/games/{game['id']}/coach-requests",
        json=payload,
        headers={**headers, "Idempotency-Key": key or str(uuid4())},
    )


def setup_analysis(app, http, headers):
    game = create(http, headers)
    move(http, game, headers)
    accepted = submit(http, game, headers)
    assert accepted.status_code == 202
    assert (
        asyncio.run(
            AnalysisWorker(
                app.state.database_factory, AnalysisEngine(), METADATA
            ).run_one()
        )
        == "done"
    )
    return game, accepted.json()


def test_coach_is_sql_backed_grounded_principal_scoped_and_survives_restart(settings):
    app = create_app(settings)
    with TestClient(app) as http:
        headers = login(http)
        game, analysis = setup_analysis(app, http, headers)
        request, key = body(game, analysis), str(uuid4())
        accepted = post(http, game, request, headers, key=key)
        assert accepted.status_code == 202, accepted.text
        validator(
            "https://mlchess.local/contracts/coach/v1.yaml#/$defs/CoachJobV1"
        ).validate(accepted.json())
        assert post(http, game, request, headers, key=key).json() == accepted.json()
        assert (
            post(http, game, request, headers).json()["job_id"]
            == accepted.json()["job_id"]
        )
        assert (
            post(
                http, game, {**request, "language": "en"}, headers, key=key
            ).status_code
            == 409
        )
        executor = CoachWorker(app.state.database_factory)
        assert asyncio.run(executor.run_one()) == "done"
        path = f"/api/v1/games/{game['id']}/coach-requests/{accepted.json()['job_id']}"
        ready = http.get(path)
        assert ready.status_code == 200, ready.text
        validator(
            "https://mlchess.local/contracts/coach/v1.yaml#/$defs/CoachJobV1"
        ).validate(ready.json())
        assert ready.json()["status"] == "ready"
        assert ready.json()["explanation"]["fallback_used"] is False, ready.text
        assert ready.json()["explanation"]["model_id"] == "verified-rules-v1"
        assert post(http, game, request, headers, key=key).json() == accepted.json()
        cookies = dict(http.cookies)
        login(http, "Bob")
        assert http.get(path).status_code == 403
        assert (
            http.get("/api/v1/coach-requests/" + accepted.json()["job_id"]).status_code
            == 404
        )

        async def events():
            async with app.state.database_factory() as session:
                return list(
                    await session.scalars(
                        select(GameEvent).where(
                            GameEvent.game_id == UUID(game["id"]),
                            GameEvent.event_type == "coach.ready",
                        )
                    )
                )

        assert len(asyncio.run(events())) == 1
    with TestClient(create_app(settings)) as restarted:
        restarted.cookies.update(cookies)
        assert restarted.get(path).json() == ready.json()


def test_undo_rejects_job_read_and_fences_late_provider_result(settings):
    app = create_app(settings)
    with TestClient(app) as http:
        headers = login(http)
        game, analysis = setup_analysis(app, http, headers)
        accepted = post(http, game, body(game, analysis), headers)
        executor = CoachWorker(app.state.database_factory)
        lease = asyncio.run(executor.claim())
        request, facts, _model = asyncio.run(executor.position(lease))
        explanation = RulesCoachProvider().explain(request)
        undo = http.post(
            f"/api/v1/games/{game['id']}/takeback",
            json={"expected_version": 1, "plies": 1, "client_action_id": str(uuid4())},
            headers=headers,
        )
        assert undo.status_code == 200
        assert asyncio.run(executor.apply(lease, explanation, None)) == "stale"
        assert (
            http.get(
                f"/api/v1/games/{game['id']}/coach-requests/{accepted.json()['job_id']}"
            ).status_code
            == 409
        )
        assert post(http, game, body(game, analysis), headers).status_code == 409


def test_context_is_strict_and_requires_completed_server_analysis(settings):
    app = create_app(settings)
    with TestClient(app) as http:
        headers = login(http)
        game = create(http, headers)
        move(http, game, headers)
        analysis = submit(http, game, headers).json()
        request = body(game, analysis)
        assert post(http, game, request, headers).status_code == 409
        for change in (
            {"analysis": {}},
            {"revision": True},
            {"schema_version": True},
            {"ply": 1.0},
            {"analysis_id": "bad"},
            {"student_context_version": None},
        ):
            assert post(http, game, {**request, **change}, headers).status_code == 422
        assert (
            post(http, game, {**request, "game_id": str(uuid4())}, headers).status_code
            == 409
        )


def test_provider_process_failure_returns_grounded_fallback_without_secret(
    settings, monkeypatch
):
    import subprocess

    app = create_app(settings)
    with TestClient(app) as http:
        headers = login(http)
        game, analysis = setup_analysis(app, http, headers)
        post(http, game, body(game, analysis), headers)
        executor = CoachWorker(app.state.database_factory)
        lease = asyncio.run(executor.claim())
        request, facts, _model = asyncio.run(executor.position(lease))

        def unavailable(*args, **kwargs):
            assert kwargs["timeout"] == 8
            assert "MLCHESS_DATABASE_URL" not in kwargs["env"]
            raise subprocess.TimeoutExpired("private-command-secret", 8)

        monkeypatch.setattr(subprocess, "run", unavailable)
        explanation, code = execute(
            RulesCoachProvider(),
            CoachJob(id=str(lease.id), request=request, cache_key="test"),
            facts,
        )
        assert explanation["fallback_used"] and "secret" not in str(explanation)
        assert code == "PROVIDER_UNAVAILABLE"
        assert asyncio.run(executor.apply(lease, explanation, code)) == "done"


def test_same_game_participant_cannot_read_another_students_coach_job(settings):
    from urllib.parse import parse_qs, urlsplit

    app = create_app(settings.model_copy(update={"invitation_secret": "x" * 43}))
    with TestClient(app) as alice, TestClient(app) as bob:
        ah, bh = login(alice), login(bob, "Bob")
        game = alice.post(
            "/api/v1/games",
            json={"mode": "friend", "time_control": None},
            headers={**ah, "Idempotency-Key": str(uuid4())},
        ).json()
        invite = alice.post(
            "/api/v1/invitations",
            json={"game_id": game["id"]},
            headers={**ah, "Idempotency-Key": str(uuid4())},
        ).json()
        token = parse_qs(urlsplit(invite["invite_url"]).fragment)["token"][0]
        accepted = bob.post(
            f"/api/v1/invitations/{invite['invite_id']}/accept",
            json={"token": token},
            headers={**bh, "Idempotency-Key": str(uuid4())},
        )
        assert accepted.status_code == 200
        move(alice, game, ah, version=1)
        arbitrary = body(game, {"id": str(uuid4())})
        assert post(alice, game, arbitrary, ah).status_code == 403
        assert post(bob, game, arbitrary, bh).status_code == 403
        assert (
            bob.post(
                f"/api/v1/games/{game['id']}/resign",
                json={"expected_version": 2},
                headers={**bh, "Idempotency-Key": str(uuid4())},
            ).status_code
            == 200
        )
        analysis = submit(alice, game, ah).json()
        assert (
            asyncio.run(
                AnalysisWorker(
                    app.state.database_factory, AnalysisEngine(), METADATA
                ).run_one()
            )
            == "done"
        )
        request = body(game, analysis)
        job = post(alice, game, request, ah).json()
        path = f"/api/v1/games/{game['id']}/coach-requests/{job['job_id']}"
        assert bob.get(path).status_code == 403
        own = post(bob, game, request, bh)
        assert own.status_code == 202
        assert own.json()["job_id"] != job["job_id"]
