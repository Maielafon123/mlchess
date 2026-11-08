"""Real row-lock races and queue separation for durable analysis."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
import os
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from backend.app.analysis.worker import AnalysisWorker
from backend.app.infra.models import Analysis, GameEvent, WorkerJob
from backend.app.workers.runner import GameplayWorker, FakeEngine
from backend.tests.analysis.helpers import AnalysisEngine, METADATA, move
from backend.tests.games.test_http_games import create, login

pytestmark = pytest.mark.skipif(
    not os.environ.get("MLCHESS_TEST_DATABASE_URL"),
    reason="Disposable PostgreSQL URL not configured",
)


def test_concurrent_analysis_keys_share_one_job_and_lease(pg_app):
    with TestClient(pg_app) as http:
        headers = login(http)
        game = create(http, headers)
        move(http, game, headers)
        actor = UUID(http.get("/api/v1/me").json()["id"])

        def submit():
            return asyncio.run(
                pg_app.state.analysis_service.submit(
                    UUID(game["id"]),
                    actor,
                    uuid4(),
                    {"ply": 1, "analysis_level": "quick"},
                )
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: submit(), range(2)))
        assert results[0]["id"] == results[1]["id"]

        async def race():
            first, second = [
                AnalysisWorker(
                    pg_app.state.database_factory, AnalysisEngine(), METADATA
                )
                for _ in range(2)
            ]
            leases = await asyncio.gather(first.claim(), second.claim())
            assert sum(lease is not None for lease in leases) == 1
            async with pg_app.state.database_factory() as session:
                assert (
                    await session.scalar(select(func.count()).select_from(Analysis))
                    == 1
                )
                assert (
                    len(
                        list(
                            await session.scalars(
                                select(WorkerJob).where(WorkerJob.queue == "analysis")
                            )
                        )
                    )
                    == 1
                )

        asyncio.run(race())


def test_gameplay_can_advance_without_invalidating_an_earlier_analysis(pg_app):
    from backend.app.analysis.evaluate import evaluate
    from contracts.validate import check_analysis_fixture

    with TestClient(pg_app) as http:
        headers = login(http)
        game = create(http, headers)
        move(http, game, headers)
        response = http.post(
            f"/api/v1/games/{game['id']}/analysis-requests",
            json={"ply": 1, "analysis_level": "quick"},
            headers={**headers, "Idempotency-Key": str(uuid4())},
        )
        assert response.status_code == 202

        async def exercise():
            analysis = AnalysisWorker(
                pg_app.state.database_factory, AnalysisEngine(), METADATA
            )
            lease = await analysis.claim()
            slice_, level = await analysis.position(lease)
            result = evaluate(
                analysis.engine,
                slice_,
                analysis_id=lease.id,
                game_id=lease.game_id,
                revision=lease.revision,
                level=level,
                metadata=METADATA,
                created_at="2026-11-09T00:00:00Z",
            )
            gameplay = GameplayWorker(pg_app.state.database_factory, FakeEngine())
            assert await gameplay.run_one() == "done"
            assert await analysis.apply(lease, result) == "done"
            assert await analysis.apply(lease, result) == "lost"
            async with pg_app.state.database_factory() as session:
                seq = list(
                    await session.scalars(
                        select(GameEvent.seq)
                        .where(GameEvent.game_id == UUID(game["id"]))
                        .order_by(GameEvent.seq)
                    )
                )
                assert seq == list(range(1, len(seq) + 1))

        asyncio.run(exercise())
        result = http.get(f"/api/v1/games/{game['id']}/analysis/1")
        assert result.status_code == 200
        check_analysis_fixture(result.json())
        assert http.get(f"/api/v1/games/{game['id']}").json()["ply"] == 2
