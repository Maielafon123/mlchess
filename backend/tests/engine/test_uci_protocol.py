from pathlib import Path
from types import SimpleNamespace
import sys

import chess
import chess.engine
import pytest

from backend.app.engine.adapter import EngineBudget, EngineError, UciEngineAdapter


class FakeProtocol:
    options = {"Threads": None, "Hash": None, "Skill Level": None}

    def __init__(self, *, timeout=False, illegal_pv=False):
        self.timeout, self.illegal_pv = timeout, illegal_pv
        self.closed = False
        self.board = None

    def configure(self, options):
        pass

    def play(self, board, limit, **kwargs):
        self.board = board
        if self.timeout:
            raise TimeoutError
        return SimpleNamespace(
            move=chess.Move.from_uci("e7e5"),
            info={
                "score": chess.engine.PovScore(chess.engine.Cp(25), chess.BLACK),
                "depth": 4,
            },
        )

    def analyse(self, board, limit, **kwargs):
        pv = [
            chess.Move.from_uci("e2e4"),
            chess.Move.from_uci("e2e3" if self.illegal_pv else "e7e5"),
        ]
        return [
            {
                "pv": pv,
                "score": chess.engine.PovScore(chess.engine.Mate(2), chess.WHITE),
                "depth": 5,
            }
        ]

    def quit(self):
        pass

    def close(self):
        self.closed = True


def adapter(monkeypatch, protocol):
    monkeypatch.setattr(
        chess.engine.SimpleEngine, "popen_uci", lambda *args, **kwargs: protocol
    )
    return UciEngineAdapter(Path(sys.executable))


def test_uci_passes_full_history_and_normalizes_score_to_white(monkeypatch):
    protocol = FakeProtocol()
    engine = adapter(monkeypatch, protocol)
    board = chess.Board()
    board.push_uci("e2e4")
    result = engine.choose_move(
        board, budget=EngineBudget(time_ms=20), profile="casual"
    )
    assert result.uci == "e7e5" and result.score.cp == -25
    assert len(protocol.board.move_stack) == 1
    engine.stop()


def test_timeout_closes_engine_and_is_sanitized(monkeypatch):
    protocol = FakeProtocol(timeout=True)
    engine = adapter(monkeypatch, protocol)
    with pytest.raises(EngineError, match="timed out"):
        engine.choose_move(chess.STARTING_FEN, budget=EngineBudget(depth=2))
    assert protocol.closed and engine._engine is None


def test_multipv_replays_legal_lines_and_keeps_mate_distinct(monkeypatch):
    engine = adapter(monkeypatch, FakeProtocol())
    lines = engine.analyze(chess.Board(), budget=EngineBudget(time_ms=20), multipv=1)
    assert lines[0].pv_uci == ("e2e4", "e7e5")
    assert lines[0].score.mate == 2 and lines[0].score.cp is None
    engine.stop()
    protocol = FakeProtocol(illegal_pv=True)
    engine = adapter(monkeypatch, protocol)
    with pytest.raises(EngineError):
        engine.analyze(chess.Board(), budget=EngineBudget(depth=1), multipv=1)
    assert protocol.closed


def test_boolean_budget_cannot_bypass_integer_bounds():
    with pytest.raises(ValueError):
        EngineBudget(depth=True)
