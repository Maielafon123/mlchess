"""Real PostgreSQL actor-lock races: one grade, private reset, exact replay."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
import os
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from backend.app.infra.models import (
    PuzzleAttemptRow,
    LearningReceiptRow,
    StudentSkillRow,
)
from backend.app.infra.problems import PublicProblem
from backend.app.learning.catalog import seed_test_catalog
from backend.tests.games.test_http_games import login

pytestmark = pytest.mark.skipif(
    not os.environ.get("MLCHESS_TEST_DATABASE_URL"),
    reason="Disposable PostgreSQL URL not configured",
)


def test_concurrent_learning_commands_grade_and_count_once(pg_app):
    with TestClient(pg_app) as http:
        asyncio.run(seed_test_catalog(pg_app.state.database_factory))
        login(http)
        actor = UUID(http.get("/api/v1/me").json()["id"])
        body = {
            "schema_version": 1,
            "learning_epoch": 0,
            "attempt_id": "same-attempt",
            "uci": "d1d8",
            "session_number": 0,
            "expected_ply": 0,
        }

        def submit(_):
            return asyncio.run(
                pg_app.state.learning_service.command(
                    "attempt", actor, uuid4(), body, target="back-rank"
                )
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(submit, range(2)))
        assert results[0] == results[1] and results[0]["completed"]

        async def verify():
            async with pg_app.state.database_factory() as session:
                assert (
                    await session.scalar(
                        select(func.count()).select_from(PuzzleAttemptRow)
                    )
                    == 1
                )
                assert (
                    await session.scalar(
                        select(func.count()).select_from(LearningReceiptRow)
                    )
                    == 2
                )
                rows = list(await session.scalars(select(StudentSkillRow)))
                assert len(rows) == 2 and all(
                    r.attempts == r.correct == 1 for r in rows
                )

        asyncio.run(verify())


def test_reset_racing_a_delayed_old_attempt_cannot_recreate_data(pg_app):
    with TestClient(pg_app) as http:
        asyncio.run(seed_test_catalog(pg_app.state.database_factory))
        login(http)
        actor = UUID(http.get("/api/v1/me").json()["id"])
        service = pg_app.state.learning_service

        def submit(operation):
            body = {"schema_version": 1, "learning_epoch": 0}
            if operation == "reset":
                body["confirm"] = True
            else:
                body.update(
                    attempt_id="old-tab", uci="d1d8", session_number=0, expected_ply=0
                )
            try:
                return asyncio.run(
                    service.command(
                        operation,
                        actor,
                        uuid4(),
                        body,
                        target="back-rank" if operation == "attempt" else None,
                    )
                )
            except PublicProblem as exc:
                assert operation == "attempt" and exc.status == 409
                return "fenced"

        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(submit, ("attempt", "reset")))
        assert http.get("/api/v1/learning/context").json()["learning_epoch"] == 1
        assert http.get("/api/v1/learning/export").json()["attempts"] == []
        assert http.get("/api/v1/learning/progress").json()["skills"] == []
