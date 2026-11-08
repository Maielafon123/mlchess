"""Frozen content is shipped by the real migration, without runtime bootstrap."""

import asyncio
import json
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import create_async_engine

from backend.app.infra.models import LessonRow, PuzzleRow, LearningProfileRow
from backend.app.learning.catalog import load_catalog
from backend.app.learning.progress_service import ProgressService


def test_fresh_migration_installs_frozen_valid_catalog(tmp_path):
    config = Config("backend/alembic.ini")
    config.attributes["ignore_environment_url"] = True
    url = "sqlite+aiosqlite:///" + (tmp_path / "migration.db").as_posix()
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")

    async def verify():
        engine = create_async_engine(url)
        async with engine.connect() as connection:
            assert (
                await connection.scalar(select(func.count()).select_from(LessonRow))
                == 8
            )
            assert (
                await connection.scalar(select(func.count()).select_from(PuzzleRow))
                == 4
            )
            assert (
                await connection.scalar(
                    select(func.count()).select_from(LearningProfileRow)
                )
                == 0
            )
        await engine.dispose()

    asyncio.run(verify())
    frozen = Path("backend/migrations/data/0005_catalog.json")
    assert json.loads(frozen.read_text(encoding="utf-8")) == load_catalog()


def test_progress_event_snapshot_does_not_change_after_later_grade():
    service = ProgressService()
    service.record_server_result("alice", "mate", result="correct", event_id="first")
    service.record_server_result("alice", "mate", result="incorrect", event_id="second")
    replay = service.record_server_result(
        "alice", "mate", result="correct", event_id="first"
    )
    assert replay.attempts == replay.correct == replay.streak == 1
    assert service.get("alice").skills["mate"].attempts == 2
    service.record_hint("alice", "mate", event_id="hint")
    service.record_hint("alice", "mate", event_id="hint")
    assert service.get("alice").skills["mate"].hints_used == 1
    assert service.get("alice").skills["mate"].attempts == 2
