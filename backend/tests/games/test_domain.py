from __future__ import annotations

import io
import random
from dataclasses import FrozenInstanceError, replace

import chess
import chess.pgn
import pytest

from backend.app.games.domain import (
    DrawNotClaimable,
    DrawOfferError,
    EndReason,
    GameDomain,
    GameError,
    GameNotActive,
    IllegalMove,
    InvalidHistory,
    Mode,
    ModeRestriction,
    NotYourTurn,
    Result,
    StaleVersion,
)

CYCLE = "g1f3 g8f6 f3g1 f6g8".split()
FIFTY = "7k/8/8/8/8/8/8/KR6 w - - {clock} 80"


def replay(line="", mode=Mode.FRIEND, **kwargs):
    return GameDomain.from_history(
        mode, line.split() if isinstance(line, str) else line, **kwargs
    )


def play(game, uci):
    return game.play(actor=game.side_to_move, uci=uci, expected_version=game.version)


def test_white_black_turns_san_and_immutable_history():
    original = GameDomain.start()
    after_white = play(original, "e2e4")
    after_black = play(after_white, "c7c5")
    assert (original.ply, original.fen, original.version) == (0, chess.STARTING_FEN, 0)
    assert after_white.side_to_move == chess.BLACK
    assert after_black.side_to_move == chess.WHITE
    assert [(item.ply, item.uci, item.san) for item in after_black.moves] == [
        (1, "e2e4", "e4"),
        (2, "c7c5", "c5"),
    ]
    assert len(after_black.board.move_stack) == 2
    with pytest.raises(FrozenInstanceError):
        after_black.version = 0


def test_solo_takeback_advances_revision_and_archives_branch():
    game = replay("e2e4 e7e5 g1f3", mode=Mode.COACH)
    rolled = game.takeback(actor=chess.WHITE, expected_version=3, plies=2)
    assert [move.uci for move in rolled.moves] == ["e2e4"]
    assert rolled.version == 4
    assert rolled.revision == 1
    assert rolled.archived_lines == (game.moves,)


@pytest.mark.parametrize("mode", [Mode.FRIEND, Mode.RATED])
def test_pvp_takeback_is_forbidden(mode):
    game = replay("e2e4 e7e5", mode=mode)
    with pytest.raises(ModeRestriction):
        game.takeback(actor=chess.WHITE, expected_version=2, plies=2)


def test_board_exposure_cannot_mutate_domain():
    game = replay("e2e4 e7e5")
    board = game.board
    board.push_uci("g1f3")
    assert game.ply == 2
    assert len(game.board.move_stack) == 2
    assert game.fen != board.fen()


@pytest.mark.parametrize(
    "uci",
    [
        "e2e5",
        "e2e2",
        "e7e5",
        "e4",
        "E2E4",
        "e2e4 ",
        "0000",
        "e2e4;ls",
        "e7e8k",
        None,
        17,
    ],
)
def test_invalid_move_is_rejected_without_state_changes(uci):
    game = GameDomain.start()
    with pytest.raises(IllegalMove):
        game.play(actor=chess.WHITE, uci=uci, expected_version=0)
    assert game.fen == chess.STARTING_FEN and game.version == 0


def test_turn_and_version_are_checked():
    game = play(GameDomain.start(), "e2e4")
    with pytest.raises(NotYourTurn):
        game.play(actor=chess.WHITE, uci="g1f3", expected_version=1)
    with pytest.raises(StaleVersion):
        game.play(actor=chess.BLACK, uci="e7e5", expected_version=0)
    with pytest.raises(StaleVersion):
        game.play(actor=chess.BLACK, uci="e7e5", expected_version=True)
    with pytest.raises(GameError):
        game.play(actor="black", uci="e7e5", expected_version=1)


@pytest.mark.parametrize(
    "line,uci,san",
    [
        ("e2e4 e7e5 g1f3 b8c6 f1c4 g8f6", "e1g1", "O-O"),
        ("d2d4 d7d5 b1c3 b8c6 c1f4 c8f5 d1d2 d8d7", "e1c1", "O-O-O"),
        ("e2e4 e7e5 g1f3 b8c6 f1c4 g8f6 e1g1 f8c5 h2h3", "e8g8", "O-O"),
    ],
)
def test_standard_castling(line, uci, san):
    game = play(replay(line), uci)
    assert game.moves[-1].san == san
    assert (
        game.board.piece_at(
            chess.F1 if uci == "e1g1" else chess.D1 if uci == "e1c1" else chess.F8
        ).piece_type
        == chess.ROOK
    )


def test_rook_square_castling_notation_is_not_accepted():
    game = replay("e2e4 e7e5 g1f3 b8c6 f1c4 g8f6")
    with pytest.raises(IllegalMove):
        play(game, "e1h1")


def test_en_passant_removes_the_actual_captured_pawn():
    game = play(replay("e2e4 a7a6 e4e5 d7d5"), "e5d6")
    assert game.moves[-1].san == "exd6"
    assert game.board.piece_at(chess.D5) is None
    assert game.board.piece_at(chess.D6) == chess.Piece(chess.PAWN, chess.WHITE)
    assert game.board.halfmove_clock == 0


@pytest.mark.parametrize("piece", [chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT])
def test_promotion_and_underpromotion(piece):
    game = replay("a2a4 h7h5 a4a5 h5h4 a5a6 h4h3 a6b7 h3g2")
    game = play(game, "b7a8" + chess.piece_symbol(piece))
    assert game.board.piece_at(chess.A8) == chess.Piece(piece, chess.WHITE)
    assert game.moves[-1].san.startswith("bxa8=")


def test_black_underpromotion():
    game = replay("h2h4 a7a5 h4h5 a5a4 h5h6 a4a3 h6g7 a3b2 g7h8q")
    game = play(game, "b2a1n")
    assert game.board.piece_at(chess.A1) == chess.Piece(chess.KNIGHT, chess.BLACK)
    assert game.side_to_move == chess.WHITE


def test_checkmate_finishes_only_once_and_prevents_commands():
    game = replay("f2f3 e7e5 g2g4 d8h4")
    assert (game.result, game.termination) == (Result.BLACK, EndReason.CHECKMATE)
    assert game.moves[-1].san == "Qh4#"
    with pytest.raises(GameNotActive):
        game.play(actor=chess.WHITE, uci="a2a3", expected_version=4)
    with pytest.raises(GameNotActive):
        game.resign(actor=chess.WHITE, expected_version=4)


@pytest.mark.parametrize(
    "fen,result,reason",
    [
        ("7k/6Q1/6K1/8/8/8/8/8 b - - 0 1", Result.WHITE, EndReason.CHECKMATE),
        ("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1", Result.DRAW, EndReason.STALEMATE),
        ("7k/8/6K1/8/8/8/8/8 w - - 0 1", Result.DRAW, EndReason.INSUFFICIENT_MATERIAL),
        (FIFTY.format(clock=150), Result.DRAW, EndReason.SEVENTYFIVE_MOVES),
    ],
)
def test_terminal_seed_positions(fen, result, reason):
    game = GameDomain.start(initial_fen=fen)
    assert (game.status, game.result, game.termination) == ("finished", result, reason)


@pytest.mark.parametrize("mode", list(Mode))
def test_threefold_is_claimable_not_automatic_in_any_mode(mode):
    game = replay(CYCLE * 2, mode)
    assert game.board.is_repetition(3)
    assert game.result is None
    claimed = game.claim_draw(actor=chess.WHITE, expected_version=game.version)
    assert (claimed.result, claimed.termination) == (
        Result.DRAW,
        EndReason.THREEFOLD_CLAIM,
    )
    assert claimed.version == game.version + 1
    assert game.result is None


def test_fen_alone_cannot_prove_threefold_history():
    game = replay(CYCLE * 2)
    fen_only = GameDomain.start(initial_fen=game.fen)
    assert not fen_only.board.is_repetition(3)
    with pytest.raises(DrawNotClaimable):
        fen_only.claim_draw(actor=chess.WHITE, expected_version=0)
    restored = GameDomain.from_history(game.mode, [move.uci for move in game.moves])
    assert restored.board.is_repetition(3)


def test_claim_without_an_indicated_move_requires_current_repetition():
    game = replay((CYCLE * 2)[:-1])
    assert game.board.can_claim_threefold_repetition()
    assert not game.board.is_repetition(3)
    with pytest.raises(DrawNotClaimable):
        game.claim_draw(actor=chess.BLACK, expected_version=game.version)


def test_draw_claim_requires_the_player_to_move():
    game = replay(CYCLE * 2)
    with pytest.raises(NotYourTurn):
        game.claim_draw(actor=chess.BLACK, expected_version=game.version)


def test_fivefold_is_automatic_but_fourfold_is_not():
    assert replay(CYCLE * 3).result is None
    game = replay(CYCLE * 4)
    assert (game.result, game.termination) == (
        Result.DRAW,
        EndReason.FIVEFOLD_REPETITION,
    )


@pytest.mark.parametrize("clock", [100, 149])
def test_fifty_moves_requires_explicit_claim(clock):
    game = GameDomain.start(initial_fen=FIFTY.format(clock=clock))
    assert game.result is None
    claimed = game.claim_draw(actor=chess.WHITE, expected_version=0)
    assert claimed.termination == EndReason.FIFTY_MOVES_CLAIM


def test_prospective_fifty_move_claim_is_not_implicitly_accepted():
    game = GameDomain.start(initial_fen=FIFTY.format(clock=99))
    assert game.board.can_claim_fifty_moves()
    assert not game.board.is_fifty_moves()
    with pytest.raises(DrawNotClaimable):
        game.claim_draw(actor=chess.WHITE, expected_version=0)


def test_seventyfive_after_quiet_move_is_automatic():
    game = play(GameDomain.start(initial_fen=FIFTY.format(clock=149)), "b1b2")
    assert game.termination == EndReason.SEVENTYFIVE_MOVES


def test_mate_takes_precedence_over_seventyfive_moves():
    game = GameDomain.start(initial_fen="7k/8/5KQ1/8/8/8/8/8 w - - 149 80")
    game = play(game, "g6g7")
    assert game.board.halfmove_clock == 150
    assert (game.result, game.termination) == (Result.WHITE, EndReason.CHECKMATE)


def test_pawn_move_resets_fifty_move_counter():
    game = GameDomain.start(initial_fen="7k/8/8/8/8/8/P7/KR6 w - - 99 80")
    game = play(game, "a2a3")
    assert game.board.halfmove_clock == 0
    with pytest.raises(DrawNotClaimable):
        game.claim_draw(actor=chess.BLACK, expected_version=1)


@pytest.mark.parametrize("mode", [Mode.FRIEND, Mode.RATED])
@pytest.mark.parametrize("actor", [chess.WHITE, chess.BLACK])
def test_only_opponent_can_accept_draw_offer(mode, actor):
    game = GameDomain.start(mode)
    offered = game.offer_draw(actor=actor, expected_version=0)
    assert offered.draw_offer is actor
    with pytest.raises(DrawOfferError):
        offered.accept_draw(actor=actor, expected_version=1)
    accepted = offered.accept_draw(actor=not actor, expected_version=1)
    assert (accepted.result, accepted.termination) == (
        Result.DRAW,
        EndReason.DRAW_AGREEMENT,
    )
    assert accepted.draw_offer is None and accepted.version == 2


def test_offer_survives_offerer_move_and_opponent_move_declines_it():
    offered = GameDomain.start().offer_draw(actor=chess.WHITE, expected_version=0)
    after_white = play(offered, "e2e4")
    assert after_white.draw_offer is chess.WHITE
    after_black = play(after_white, "e7e5")
    assert after_black.draw_offer is None
    with pytest.raises(DrawOfferError):
        after_black.accept_draw(actor=chess.WHITE, expected_version=3)


def test_draw_offers_cannot_be_replaced_or_accepted_without_offer():
    game = GameDomain.start()
    with pytest.raises(DrawOfferError):
        game.accept_draw(actor=chess.WHITE, expected_version=0)
    game = game.offer_draw(actor=chess.BLACK, expected_version=0)
    with pytest.raises(DrawOfferError):
        game.offer_draw(actor=chess.WHITE, expected_version=1)


@pytest.mark.parametrize("mode", [Mode.AI, Mode.COACH])
def test_human_draw_offer_lifecycle_is_pvp_only(mode):
    game = GameDomain.start(mode)
    with pytest.raises(ModeRestriction):
        game.offer_draw(actor=chess.WHITE, expected_version=0)
    with pytest.raises(ModeRestriction):
        game.accept_draw(actor=chess.WHITE, expected_version=0)


@pytest.mark.parametrize("actor", [chess.WHITE, chess.BLACK])
def test_resignation_selects_other_winner_and_clears_offer(actor):
    game = GameDomain.start().offer_draw(actor=actor, expected_version=0)
    game = game.resign(actor=actor, expected_version=1)
    assert game.result == (Result.BLACK if actor else Result.WHITE)
    assert game.termination == EndReason.RESIGNATION
    assert game.draw_offer is None


@pytest.mark.parametrize("line", ["e2e5", "0000", "f2f3 e7e5 g2g4 d8h4 a2a3"])
def test_restore_rejects_illegal_history_or_continuation_after_mate(line):
    with pytest.raises(InvalidHistory):
        replay(line)


@pytest.mark.parametrize("fen", ["not a fen", "8/8/8/8/8/8/8/8 w - - 0 1"])
def test_invalid_seed_is_rejected(fen):
    with pytest.raises(InvalidHistory):
        GameDomain.start(initial_fen=fen)


def test_restore_checks_san_and_cannot_invent_a_claimed_draw():
    game = replay("e2e4 e7e5")
    with pytest.raises(InvalidHistory):
        replace(game, moves=(replace(game.moves[0], san="Nf3"), game.moves[1]))
    with pytest.raises(InvalidHistory):
        replace(
            game, result=Result.DRAW, termination=EndReason.THREEFOLD_CLAIM, version=3
        )
    with pytest.raises(InvalidHistory):
        replace(game, version=1)


@pytest.mark.parametrize(
    "line,expected_result", [("e2e4 c7c5", "*"), ("f2f3 e7e5 g2g4 d8h4", "0-1")]
)
def test_pgn_export_roundtrips_history_and_result(line, expected_result):
    game = replay(line)
    parsed = chess.pgn.read_game(io.StringIO(game.to_pgn()))
    assert parsed.headers["Result"] == expected_result
    assert [move.uci() for move in parsed.mainline_moves()] == line.split()
    assert parsed.end().board().fen() == game.fen


def test_seed_pgn_includes_initial_position_and_manual_result():
    game = play(GameDomain.start(initial_fen=FIFTY.format(clock=0)), "b1b2")
    game = game.resign(actor=chess.BLACK, expected_version=1)
    parsed = chess.pgn.read_game(io.StringIO(game.to_pgn()))
    assert parsed.headers["SetUp"] == "1"
    assert parsed.headers["FEN"] == game.initial_fen
    assert parsed.headers["Result"] == "1-0"
    assert parsed.end().board().fen() == game.fen


def test_reproducible_legal_sequences_match_python_chess():
    rng = random.Random(20261107)
    for _ in range(3):
        domain = GameDomain.start(Mode.RATED)
        board = chess.Board()
        for _ in range(64):
            if board.outcome(claim_draw=False) is not None:
                break
            move = rng.choice(list(board.legal_moves))
            previous = domain
            previous_fen = domain.fen
            domain = play(domain, move.uci())
            board.push(move)
            assert domain.fen == board.fen()
            assert len(domain.board.move_stack) == len(board.move_stack)
            assert previous.fen == previous_fen
            assert (domain.result is not None) == (
                board.outcome(claim_draw=False) is not None
            )


def test_restore_cannot_import_alternative_castling_notation():
    with pytest.raises(InvalidHistory):
        replay("e2e4 e7e5 g1f3 b8c6 f1c4 g8f6 e1h1")
