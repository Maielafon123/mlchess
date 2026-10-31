from __future__ import annotations

import chess
import numpy as np
import pytest
import torch

from chess_ai.mcts import MCTS, evaluate_position, terminal_value
from chess_ai.model import PolicyValueNet


def uniform_evaluator(_: object, board: chess.Board, __: torch.device) -> tuple[np.ndarray, np.ndarray, float]:
    from chess_ai.encoding import legal_action_indices

    actions = legal_action_indices(board).astype(np.int64)
    return actions, np.full(len(actions), 1 / len(actions), dtype=np.float32), 0.0


def test_evaluate_position_masks_to_legal_actions() -> None:
    model = PolicyValueNet(width=8, blocks=1)
    actions, priors, value = evaluate_position(model, chess.Board(), torch.device("cpu"))
    assert len(actions) == 20
    assert np.isclose(priors.sum(), 1.0)
    assert -1.0 <= value <= 1.0


def test_mcts_returns_legal_move_and_counts_visits() -> None:
    board = chess.Board()
    search = MCTS(None, "cpu", evaluator=uniform_evaluator)  # type: ignore[arg-type]
    root = search.search(board, simulations=8)
    assert root.visit_count == 8
    assert sum(child.visit_count for child in root.children.values()) == 7
    assert search.choose_move(board, simulations=4) in board.legal_moves


def test_terminal_value_and_terminal_search() -> None:
    board = chess.Board("7k/6Q1/6K1/8/8/8/8/8 b - - 0 1")
    assert board.is_checkmate()
    assert terminal_value(board) == -1.0
    search = MCTS(None, "cpu", evaluator=uniform_evaluator)  # type: ignore[arg-type]
    assert search.search(board, simulations=2).visit_count == 2
    with pytest.raises(ValueError, match="already over"):
        search.choose_move(board, simulations=1)
