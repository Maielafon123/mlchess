from __future__ import annotations

from uuid import uuid4

from backend.app.games.domain import GameDomain, Mode
from backend.app.workers.gameplay import EngineMoveJob, can_apply_engine_job


def test_engine_job_requires_matching_version_and_revision():
    game = GameDomain.start(Mode.AI)
    job = EngineMoveJob(uuid4(), 0, 0, game.side_to_move, "e2e4")
    assert can_apply_engine_job(game, job) is True
    active = game.play(actor=game.side_to_move, uci="e2e4", expected_version=0)
    assert can_apply_engine_job(active, job) is False
