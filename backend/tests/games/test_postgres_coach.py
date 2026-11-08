"""Persistent coaching deduplication and late-delivery fencing on PostgreSQL."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
import os
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from backend.app.analysis.worker import AnalysisWorker
from backend.app.coach.providers.rules import RulesCoachProvider
from backend.app.coach.worker import CoachWorker
from backend.app.infra.models import CoachExplanation, GameEvent
from backend.tests.analysis.helpers import AnalysisEngine, METADATA, move, submit
from backend.tests.coach.test_durable_coach import body
from backend.tests.games.test_http_games import create, login

pytestmark = pytest.mark.skipif(
    not os.environ.get("MLCHESS_TEST_DATABASE_URL"),
    reason="Disposable PostgreSQL URL not configured",
)


def test_concurrent_coach_requests_share_one_job_and_commit_once(pg_app):
    with TestClient(pg_app) as http:
        headers = login(http)
        game = create(http, headers)
        move(http, game, headers)
        analysis = submit(http, game, headers).json()
        factory = pg_app.state.database_factory
        assert (
            asyncio.run(AnalysisWorker(factory, AnalysisEngine(), METADATA).run_one())
            == "done"
        )
        request = body(game, analysis)
        actor = UUID(http.get("/api/v1/me").json()["id"])

        def accept():
            return asyncio.run(
                pg_app.state.coach_service.submit(actor, uuid4(), request)
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: accept(), range(2)))
        assert results[0]["job_id"] == results[1]["job_id"]

        async def exercise():
            worker = CoachWorker(factory)
            lease = await worker.claim()
            request_, facts = await worker.position(lease)
            explanation = RulesCoachProvider().explain(request_)
            assert await worker.apply(lease, explanation, None) == "done"
            assert await worker.apply(lease, explanation, None) == "lost"
            async with factory() as session:
                assert (
                    await session.scalar(
                        select(func.count()).select_from(CoachExplanation)
                    )
                    == 1
                )
                assert (
                    await session.scalar(
                        select(func.count())
                        .select_from(GameEvent)
                        .where(GameEvent.event_type == "coach.ready")
                    )
                    == 1
                )

        asyncio.run(exercise())
