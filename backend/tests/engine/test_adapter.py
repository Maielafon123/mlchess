from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.engine.adapter import EngineBudget, EngineScore, sha256_file


@pytest.mark.parametrize(
    "kwargs", [{}, {"time_ms": 0}, {"nodes": 10_000_001}, {"depth": 65}]
)
def test_engine_budget_is_bounded(kwargs):
    with pytest.raises(ValueError):
        EngineBudget(**kwargs)


def test_score_requires_exactly_one_unit():
    with pytest.raises(ValueError):
        EngineScore("white")
    with pytest.raises(ValueError):
        EngineScore("white", cp=10, mate=1)
    assert EngineScore("black", mate=3).mate == 3


def test_hashing_is_deterministic(tmp_path: Path):
    path = tmp_path / "engine"
    path.write_bytes(b"uci")
    assert len(sha256_file(path)) == 64
