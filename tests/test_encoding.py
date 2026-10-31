from __future__ import annotations

import random

import chess
import numpy as np
import pytest

from chess_ai.encoding import (
    ACTION_SIZE,
    action_to_move,
    actions_are_unique,
    encode_board,
    legal_action_indices,
    mirror_action,
    mirror_tensor,
    move_to_action,
)


def assert_round_trip(board: chess.Board) -> None:
    actions = []
    for move in board.legal_moves:
        action = move_to_action(board, move)
        assert 0 <= action < ACTION_SIZE
        assert action_to_move(board, action) == move
        actions.append(action)
    assert len(actions) == len(set(actions))
    assert actions_are_unique(board)


def test_round_trip_across_random_game_positions() -> None:
    rng = random.Random(7)
    board = chess.Board()
    for _ in range(180):
        if board.is_game_over():
            board = chess.Board()
        assert_round_trip(board)
        board.push(rng.choice(list(board.legal_moves)))


@pytest.mark.parametrize(
    "fen",
    [
        "r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1",
        "4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1",
        "7k/P7/8/8/8/8/7p/4K3 w - - 0 1",
        "4k3/7P/8/8/8/8/p7/7K b - - 0 1",
    ],
)
def test_round_trip_special_moves(fen: str) -> None:
    assert_round_trip(chess.Board(fen))


def test_black_position_is_canonicalised_for_side_to_move() -> None:
    board = chess.Board()
    board.push_uci("e2e4")
    state = encode_board(board)

    # Black to move: black pawn e7 becomes an own pawn on e2; White's pawn e4
    # becomes an opponent pawn on e5 after vertical mirroring.
    assert state[0, 1, 4] == 1.0
    assert state[6, 4, 4] == 1.0
    assert state.shape == (20, 8, 8)


def test_action_and_tensor_mirror_are_involutions() -> None:
    board = chess.Board()
    state = encode_board(board)
    assert np.array_equal(mirror_tensor(mirror_tensor(state)), state)
    for action in legal_action_indices(board):
        assert mirror_action(mirror_action(int(action))) == int(action)

