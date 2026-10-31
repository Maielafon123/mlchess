from __future__ import annotations

import io

import chess
import chess.pgn

from chess_ai.stream import iter_examples_from_game, parse_comment


def read_game(pgn: str) -> chess.pgn.Game:
    game = chess.pgn.read_game(io.StringIO(pgn))
    assert game is not None
    return game


def test_comment_parses_q_and_legal_best_move() -> None:
    board = chess.Board()
    parsed = parse_comment("0.25 e2e4", board)
    assert parsed.q_value == 0.25
    assert parsed.best_move == chess.Move.from_uci("e2e4")


def test_comment_normalises_rook_square_castling_notation() -> None:
    board = chess.Board("r2qk2r/1p2bp1p/p1b3p1/3pP2n/Np5P/1B2PN2/P4PP1/R2Q1RK1 b kq - 3 18")
    parsed = parse_comment("0.09 e8h8", board)
    assert parsed.best_move == chess.Move.from_uci("e8g8")


def test_examples_keep_q_wdl_and_educational_metadata() -> None:
    game = read_game(
        """[Event "Lc0 Training Data"]
[Result "1-0"]
[Opening "King's Pawn Game"]
[Themes "fork short"]
[Rating "1650"]

1. e4 { 0.25 d2d4 } e5 { -0.20 } 2. Nf3 1-0
"""
    )
    examples = list(iter_examples_from_game(game, game_id="fixture"))
    assert len(examples) == 3
    assert examples[0].value_target == 0.25
    assert examples[0].wdl_target == 1
    assert examples[1].value_target == -0.20
    assert examples[1].wdl_target == -1
    assert examples[0].opening == "King's Pawn Game"
    assert examples[0].themes == ("fork", "short")
    assert examples[0].rating == 1650
    assert examples[0].policy_action != examples[0].action


def test_chess960_is_excluded_from_standard_stream() -> None:
    game = read_game(
        """[Event "Lc0 Training Data"]
[Result "1/2-1/2"]
[SetUp "1"]
[FEN "rkbbrnnq/pppppppp/8/8/8/8/PPPPPPPP/RKBBRNNQ w KQkq - 0 1"]
[Variant "Chess960"]

1. f4 f5 1/2-1/2
"""
    )
    assert list(iter_examples_from_game(game, game_id="chess960")) == []
