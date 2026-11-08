import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.app.analysis.evaluate import evaluate
from backend.app.analysis.worker import AnalysisWorker
from backend.app.engine.adapter import EngineError
from backend.app.infra.models import GameEvent, OutboxEvent, WorkerJob
from backend.app.main import create_app
from backend.tests.analysis.helpers import AnalysisEngine, METADATA, move, submit
from backend.tests.games.test_http_games import create, login
from contracts.validate import check_analysis_fixture, validator


def worker(app, engine=None, **kwargs):
    return AnalysisWorker(
        app.state.database_factory, engine or AnalysisEngine(), METADATA, **kwargs
    )


def completed(worker_, lease):
    slice_, level = asyncio.run(worker_.position(lease))
    return evaluate(
        worker_.engine,
        slice_,
        analysis_id=lease.id,
        game_id=lease.game_id,
        revision=lease.revision,
        level=level,
        metadata=METADATA,
        created_at="2026-11-09T00:00:00Z",
    )


def test_accept_cache_exact_replay_commit_event_and_restart(settings):
    app = create_app(settings)
    with TestClient(app) as http:
        headers = login(http)
        game = create(http, headers)
        move(http, game, headers)
        key = str(uuid4())
        accepted = submit(http, game, headers, key=key)
        assert accepted.status_code == 202, accepted.text
        validator(
            "https://mlchess.local/contracts/analysis/v1.yaml#/$defs/AnalysisJobV1"
        ).validate(accepted.json())
        assert submit(http, game, headers, key=key).json() == accepted.json()
        assert (
            submit(http, game, headers, key=key, analysis_level="deep").status_code
            == 409
        )
        assert submit(http, game, headers).json()["id"] == accepted.json()["id"]
        path = f"/api/v1/games/{game['id']}/analysis/1"
        assert http.get(path).status_code == 202
        assert asyncio.run(worker(app).run_one()) == "done"
        response = http.get(path)
        assert response.status_code == 200, response.text
        check_analysis_fixture(response.json())
        assert submit(http, game, headers, key=key).json() == accepted.json()
        cookies = dict(http.cookies)

        async def evidence():
            async with app.state.database_factory() as session:
                return list(
                    await session.scalars(
                        select(GameEvent).where(
                            GameEvent.event_type == "analysis.ready"
                        )
                    )
                )

        events = asyncio.run(evidence())
        assert (
            len(events) == 1
            and events[0].payload["payload"]["analysis_id"] == accepted.json()["id"]
        )
    with TestClient(create_app(settings)) as restarted:
        restarted.cookies.update(cookies)
        assert restarted.get(path).json() == response.json()


def test_undo_fences_inflight_result_and_old_idempotency_key(settings):
    app = create_app(settings)
    with TestClient(app) as http:
        headers = login(http)
        game = create(http, headers)
        move(http, game, headers)
        key = str(uuid4())
        assert submit(http, game, headers, key=key).status_code == 202
        executor = worker(app)
        lease = asyncio.run(executor.claim())
        result = completed(executor, lease)
        undo = http.post(
            f"/api/v1/games/{game['id']}/takeback",
            headers=headers,
            json={"expected_version": 1, "plies": 1, "client_action_id": str(uuid4())},
        )
        assert undo.status_code == 200
        assert asyncio.run(executor.apply(lease, result)) == "stale"
        move(http, game, headers, "d2d4", 2)
        assert submit(http, game, headers, key=key).status_code == 409
        assert http.get(f"/api/v1/games/{game['id']}/analysis/1").status_code == 404
        assert submit(http, game, headers).json()["revision"] == 1
        assert asyncio.run(executor.run_one()) == "done"


def test_expired_lease_recovery_fences_old_worker_and_bounds_failure(settings):
    app = create_app(settings)
    with TestClient(app) as http:
        headers = login(http)
        game = create(http, headers)
        move(http, game, headers)
        submit(http, game, headers)
        executor = worker(app)
        old = asyncio.run(executor.claim())
        result = completed(executor, old)

        async def expire():
            async with app.state.database_factory() as session, session.begin():
                job = await session.get(WorkerJob, old.id)
                job.lease_until = datetime.now(timezone.utc) - timedelta(seconds=1)

        asyncio.run(expire())
        new = asyncio.run(executor.claim())
        assert new.id == old.id and new.token != old.token
        assert asyncio.run(executor.apply(old, result)) == "lost"
        assert asyncio.run(executor.apply(new, result)) == "done"
        assert asyncio.run(executor.apply(new, result)) == "lost"

        class Broken:
            def analyze(self, *args, **kwargs):
                raise EngineError("SECRET engine internal path")

        submit(http, game, headers, analysis_level="deep")
        assert asyncio.run(worker(app, Broken(), max_attempts=1).run_one()) == "failed"
        failed = http.get(f"/api/v1/games/{game['id']}/analysis/1")
        assert failed.status_code == 202 and failed.json()["status"] == "failed"
        assert failed.json()["error"]["status"] == 503 and "SECRET" not in failed.text
        # A new explicit request retries recovered infrastructure; no permanent
        # failed cache entry can trap the Retry button on a valid current line.
        retried = submit(http, game, headers, analysis_level="deep")
        assert retried.status_code == 202 and retried.json()["status"] == "pending"
        assert retried.json()["id"] == failed.json()["id"]
        assert asyncio.run(worker(app).run_one()) == "done"


def test_analysis_acl_csrf_phase_and_strict_input(settings):
    app = create_app(settings)
    with TestClient(app) as http:
        headers = login(http)
        game = create(http, headers)
        move(http, game, headers)
        assert submit(http, game, {"Origin": "http://testserver"}).status_code == 403
        for payload in (
            {"ply": True},
            {"ply": 1.0},
            {"ply": "1"},
            {"fen": "anything"},
            {"analysis_level": "unlimited"},
            {"ply": 999},
        ):
            assert submit(http, game, headers, **payload).status_code == 422
        friend = http.post(
            "/api/v1/games",
            json={"mode": "friend", "time_control": None},
            headers={**headers, "Idempotency-Key": str(uuid4())},
        ).json()
        assert submit(http, friend, headers).status_code == 403
        assert http.get(f"/api/v1/games/{friend['id']}/analysis/1").status_code == 403
        login(http, "Bob")
        assert (
            submit(
                http,
                game,
                {
                    "Origin": "http://testserver",
                    "X-CSRF-Token": http.cookies["mlchess_csrf"],
                },
            ).status_code
            == 403
        )
        assert http.get(f"/api/v1/games/{game['id']}/analysis/1").status_code == 403


def test_friendly_analysis_is_only_available_after_terminal_commit(settings):
    app = create_app(settings.model_copy(update={"invitation_secret": "x" * 43}))
    with TestClient(app) as alice, TestClient(app) as bob:
        ah, bh = login(alice), login(bob, "Bob")
        game = alice.post(
            "/api/v1/games",
            json={"mode": "friend", "time_control": None},
            headers={**ah, "Idempotency-Key": str(uuid4())},
        ).json()
        invitation = alice.post(
            "/api/v1/invitations",
            json={"game_id": game["id"]},
            headers={**ah, "Idempotency-Key": str(uuid4())},
        )
        assert invitation.status_code == 201, invitation.text
        from urllib.parse import urlsplit, parse_qs

        token = parse_qs(urlsplit(invitation.json()["invite_url"]).fragment)["token"][0]
        accepted = bob.post(
            f"/api/v1/invitations/{invitation.json()['invite_id']}/accept",
            json={"token": token},
            headers={**bh, "Idempotency-Key": str(uuid4())},
        )
        assert accepted.status_code == 200, accepted.text
        move(alice, game, ah, version=1)
        assert submit(alice, game, ah).status_code == 403
        assert submit(bob, game, bh).status_code == 403
        resigned = bob.post(
            f"/api/v1/games/{game['id']}/resign",
            json={"expected_version": 2},
            headers={**bh, "Idempotency-Key": str(uuid4())},
        )
        assert resigned.status_code == 200, resigned.text
        assert submit(alice, game, ah).status_code == 202
        assert asyncio.run(worker(app).run_one()) == "done"
        assert bob.get(f"/api/v1/games/{game['id']}/analysis/1").status_code == 200


def test_hourly_quota_is_durable_and_cache_hits_do_not_spend_more_work(settings):
    app = create_app(settings)
    with TestClient(app) as http:
        headers = login(http)
        game = create(http, headers)
        move(http, game, headers)
        cached = submit(http, game, headers)
        actor = http.get("/api/v1/me").json()["id"]

        async def spend_quota():
            async with app.state.database_factory() as session, session.begin():
                for _ in range(39):
                    session.add(
                        OutboxEvent(
                            aggregate_type="analysis",
                            aggregate_id=uuid4(),
                            event_type="analysis.requested",
                            payload={"actor_id": actor},
                        )
                    )

        asyncio.run(spend_quota())
        assert submit(http, game, headers).json()["id"] == cached.json()["id"]
        assert submit(http, game, headers, analysis_level="deep").status_code == 429
