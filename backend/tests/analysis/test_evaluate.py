import json
from dataclasses import replace
from uuid import uuid4

import pytest

from backend.app.analysis.evaluate import evaluate, score_json
from backend.app.analysis.service import reconstruct_position
from backend.app.engine.adapter import EngineError, EngineScore
from backend.app.games.domain import GameDomain
from backend.tests.analysis.helpers import AnalysisEngine, METADATA
from contracts.validate import ROOT, check_analysis_fixture, validator


@pytest.mark.parametrize(
    "name",
    [
        "cp-white",
        "cp-black",
        "mate",
        "capture",
        "en-passant",
        "castling",
        "promotion",
        "missed-mate",
    ],
)
def test_worker_results_prove_chess_facts_against_independent_contract_verifier(name):
    sample = json.loads(
        (ROOT / "fixtures/analysis" / f"result-{name}.json").read_text()
    )
    game = GameDomain.from_history(
        "coach", [sample["played_move_uci"]], initial_fen=sample["before_fen"]
    )
    result = evaluate(
        AnalysisEngine(),
        # Golden fixtures start at a midgame FEN; their wire ply is absolute.
        replace(reconstruct_position(game, 1), ply=sample["ply"]),
        analysis_id=uuid4(),
        game_id=uuid4(),
        revision=0,
        level="quick",
        metadata=METADATA,
        created_at="2026-11-09T00:00:00Z",
    )
    validator(
        "https://mlchess.local/contracts/analysis/v1.yaml#/$defs/AnalysisResultV1"
    ).validate(result)
    check_analysis_fixture(result)
    assert result["facts"]["material_delta"] == sample["facts"]["material_delta"]
    assert result["facts"]["checks"] == sample["facts"]["checks"]
    if name == "en-passant":
        capture = next(
            c for c in result["facts"]["verified_claims"] if c["kind"] == "capture"
        )
        assert capture["evidence"]["square"] != result["played_move_uci"][2:4]


@pytest.mark.parametrize(
    "white_mover,before,after,expected",
    [(True, 50, 20, 30), (False, -50, 20, 70), (False, 50, 20, 0)],
)
def test_cp_loss_is_always_from_the_mover_pov(white_mover, before, after, expected):
    class Scored(AnalysisEngine):
        def __init__(self):
            self.calls = 0

        def analyze(self, *args, **kwargs):
            from dataclasses import replace

            self.calls += 1
            return tuple(
                replace(
                    line,
                    score=EngineScore("white", cp=before if self.calls == 1 else after),
                )
                for line in super().analyze(*args, **kwargs)
            )

    game = GameDomain.from_history(
        "coach", ["e2e4"] if white_mover else ["e2e4", "e7e5"]
    )
    result = evaluate(
        Scored(),
        reconstruct_position(game, len(game.moves)),
        analysis_id=uuid4(),
        game_id=uuid4(),
        revision=0,
        level="deep",
        metadata=METADATA,
        created_at="2026-11-09T00:00:00Z",
    )
    assert result["cp_loss"] == expected
    check_analysis_fixture(result)


def test_bad_engine_variation_is_rejected_before_persistence():
    class Illegal(AnalysisEngine):
        def analyze(self, *args, **kwargs):
            from dataclasses import replace

            lines = list(super().analyze(*args, **kwargs))
            lines[0] = replace(lines[0], pv_uci=(lines[0].uci, "a1a8"))
            return tuple(lines)

    with pytest.raises(EngineError):
        evaluate(
            Illegal(),
            reconstruct_position(GameDomain.from_history("coach", ["e2e4"]), 1),
            analysis_id=uuid4(),
            game_id=uuid4(),
            revision=0,
            level="quick",
            metadata=METADATA,
            created_at="2026-11-09T00:00:00Z",
        )
    with pytest.raises(EngineError):
        score_json(EngineScore("black", cp=12))
