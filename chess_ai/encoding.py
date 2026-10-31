"""Canonical board and action encoding for standard chess.

The representation is always from the side-to-move's perspective.  Black
positions are mirrored vertically, so its pawns move toward increasing ranks
in exactly the same way as White's.  This lets one network play both colours.
"""

from __future__ import annotations

from collections.abc import Iterable

import chess
import numpy as np

BOARD_SIZE = 8
ACTION_PLANES = 73
ACTION_SIZE = ACTION_PLANES * BOARD_SIZE * BOARD_SIZE
INPUT_PLANES = 20

# Queen-like moves are used for sliders, kings, pawns, castling and queen
# promotions. Directions are expressed in the canonical side-to-move frame.
QUEEN_DIRECTIONS: tuple[tuple[int, int], ...] = (
    (0, 1),
    (1, 1),
    (1, 0),
    (1, -1),
    (0, -1),
    (-1, -1),
    (-1, 0),
    (-1, 1),
)
KNIGHT_DELTAS: tuple[tuple[int, int], ...] = (
    (1, 2),
    (2, 1),
    (2, -1),
    (1, -2),
    (-1, -2),
    (-2, -1),
    (-2, 1),
    (-1, 2),
)
UNDERPROMOTION_DIRECTIONS: tuple[tuple[int, int], ...] = ((-1, 1), (0, 1), (1, 1))
UNDERPROMOTION_PIECES: tuple[chess.PieceType, ...] = (
    chess.KNIGHT,
    chess.BISHOP,
    chess.ROOK,
)


def canonical_square(square: chess.Square, turn: chess.Color) -> chess.Square:
    """Return ``square`` in the side-to-move coordinate system."""
    return square if turn == chess.WHITE else chess.square_mirror(square)


def _square_from_file_rank(file_index: int, rank_index: int) -> chess.Square:
    if not 0 <= file_index < BOARD_SIZE or not 0 <= rank_index < BOARD_SIZE:
        raise ValueError(f"square is outside the board: file={file_index}, rank={rank_index}")
    return chess.square(file_index, rank_index)


def _queen_plane(dx: int, dy: int) -> int:
    distance = max(abs(dx), abs(dy))
    if distance < 1 or distance > 7 or not (dx == 0 or dy == 0 or abs(dx) == abs(dy)):
        raise ValueError(f"not a queen-like move: dx={dx}, dy={dy}")
    direction = (dx // distance, dy // distance)
    try:
        direction_index = QUEEN_DIRECTIONS.index(direction)
    except ValueError as error:
        raise ValueError(f"unknown queen direction: {direction}") from error
    return direction_index * 7 + distance - 1


def _knight_plane(dx: int, dy: int) -> int:
    try:
        return 56 + KNIGHT_DELTAS.index((dx, dy))
    except ValueError as error:
        raise ValueError(f"not a knight move: dx={dx}, dy={dy}") from error


def move_to_action(board: chess.Board, move: chess.Move) -> int:
    """Encode a legal move as one of 4672 stable policy indices.

    The action belongs to the canonical coordinates of ``board.turn``.  Queen
    promotions deliberately share the ordinary queen-like planes; only
    knight/bishop/rook promotions need dedicated planes.
    """
    # python-chess accepts the Chess960 rook-square spelling for a standard
    # castling move in some membership checks (e8h8 vs e8g8). Parsing through
    # the board canonicalises that spelling before it reaches the policy map.
    try:
        move = board.parse_uci(move.uci())
    except ValueError as error:
        raise ValueError(f"move is not legal in this position: {move.uci()}") from error

    canonical_from = canonical_square(move.from_square, board.turn)
    canonical_to = canonical_square(move.to_square, board.turn)
    from_file = chess.square_file(canonical_from)
    from_rank = chess.square_rank(canonical_from)
    to_file = chess.square_file(canonical_to)
    to_rank = chess.square_rank(canonical_to)
    dx, dy = to_file - from_file, to_rank - from_rank

    if move.promotion and move.promotion != chess.QUEEN:
        try:
            direction_index = UNDERPROMOTION_DIRECTIONS.index((dx, dy))
            piece_index = UNDERPROMOTION_PIECES.index(move.promotion)
        except ValueError as error:
            raise ValueError(f"invalid underpromotion: {move.uci()}") from error
        plane = 64 + direction_index * len(UNDERPROMOTION_PIECES) + piece_index
    elif (dx, dy) in KNIGHT_DELTAS:
        plane = _knight_plane(dx, dy)
    else:
        plane = _queen_plane(dx, dy)

    return plane * 64 + canonical_from


def action_to_move(board: chess.Board, action: int) -> chess.Move:
    """Decode an action index and verify that it is legal in ``board``."""
    if not 0 <= action < ACTION_SIZE:
        raise ValueError(f"action must be in [0, {ACTION_SIZE}), got {action}")

    plane, canonical_from = divmod(action, 64)
    from_file = chess.square_file(canonical_from)
    from_rank = chess.square_rank(canonical_from)
    promotion: chess.PieceType | None = None

    if plane < 56:
        direction = QUEEN_DIRECTIONS[plane // 7]
        distance = plane % 7 + 1
        dx, dy = direction[0] * distance, direction[1] * distance
    elif plane < 64:
        dx, dy = KNIGHT_DELTAS[plane - 56]
    else:
        underpromotion = plane - 64
        direction_index, piece_index = divmod(underpromotion, len(UNDERPROMOTION_PIECES))
        dx, dy = UNDERPROMOTION_DIRECTIONS[direction_index]
        promotion = UNDERPROMOTION_PIECES[piece_index]

    canonical_to = _square_from_file_rank(from_file + dx, from_rank + dy)
    from_square = canonical_square(canonical_from, board.turn)
    to_square = canonical_square(canonical_to, board.turn)

    # Queen promotion is encoded as a normal queen-like move. We can recover it
    # from the actual board because this decoder always receives a position.
    piece = board.piece_at(from_square)
    if promotion is None and piece and piece.piece_type == chess.PAWN and chess.square_rank(to_square) in (0, 7):
        promotion = chess.QUEEN

    move = chess.Move(from_square, to_square, promotion=promotion)
    if move not in board.legal_moves:
        raise ValueError(f"decoded action is not legal in this position: action={action}, move={move.uci()}")
    return move


def legal_action_indices(board: chess.Board) -> np.ndarray:
    """Return legal policy indices as a compact int16 array."""
    return np.asarray([move_to_action(board, move) for move in board.legal_moves], dtype=np.int16)


def mirror_action(action: int) -> int:
    """Map a canonical action through a horizontal (a↔h) board mirror."""
    if not 0 <= action < ACTION_SIZE:
        raise ValueError(f"action must be in [0, {ACTION_SIZE}), got {action}")
    plane, source = divmod(action, 64)
    mirrored_source = chess.square(7 - chess.square_file(source), chess.square_rank(source))

    if plane < 56:
        direction = QUEEN_DIRECTIONS[plane // 7]
        distance = plane % 7 + 1
        mirrored_direction = (-direction[0], direction[1])
        mirrored_plane = QUEEN_DIRECTIONS.index(mirrored_direction) * 7 + distance - 1
    elif plane < 64:
        dx, dy = KNIGHT_DELTAS[plane - 56]
        mirrored_plane = 56 + KNIGHT_DELTAS.index((-dx, dy))
    else:
        promotion = plane - 64
        direction_index, piece_index = divmod(promotion, len(UNDERPROMOTION_PIECES))
        dx, dy = UNDERPROMOTION_DIRECTIONS[direction_index]
        mirrored_plane = 64 + UNDERPROMOTION_DIRECTIONS.index((-dx, dy)) * len(UNDERPROMOTION_PIECES) + piece_index

    return mirrored_plane * 64 + mirrored_source


def mirror_tensor(state: np.ndarray) -> np.ndarray:
    """Mirror a [planes, ranks, files] encoded state across the a–h axis."""
    if state.shape != (INPUT_PLANES, BOARD_SIZE, BOARD_SIZE):
        raise ValueError(f"expected state shape {(INPUT_PLANES, BOARD_SIZE, BOARD_SIZE)}, got {state.shape}")
    return np.ascontiguousarray(np.flip(state, axis=2))


def encode_board(board: chess.Board) -> np.ndarray:
    """Encode a standard-chess position into 20 canonical feature planes.

    Planes 0–5 are own P/N/B/R/Q/K, 6–11 are opponent pieces, 12–15 are
    own/opponent castling rights, 16 is en passant, 17 is the normalised
    halfmove clock, and 18–19 indicate twofold/threefold repetition.
    """
    state = np.zeros((INPUT_PLANES, BOARD_SIZE, BOARD_SIZE), dtype=np.float32)
    us = board.turn

    for square, piece in board.piece_map().items():
        canonical = canonical_square(square, us)
        plane = piece.piece_type - 1
        if piece.color != us:
            plane += 6
        state[plane, chess.square_rank(canonical), chess.square_file(canonical)] = 1.0

    castling_rights = (
        board.has_kingside_castling_rights(us),
        board.has_queenside_castling_rights(us),
        board.has_kingside_castling_rights(not us),
        board.has_queenside_castling_rights(not us),
    )
    for offset, enabled in enumerate(castling_rights):
        if enabled:
            state[12 + offset].fill(1.0)

    if board.ep_square is not None:
        canonical_ep = canonical_square(board.ep_square, us)
        state[16, chess.square_rank(canonical_ep), chess.square_file(canonical_ep)] = 1.0

    state[17].fill(min(board.halfmove_clock, 100) / 100.0)
    if board.is_repetition(2):
        state[18].fill(1.0)
    if board.is_repetition(3):
        state[19].fill(1.0)
    return state


def actions_are_unique(board: chess.Board, moves: Iterable[chess.Move] | None = None) -> bool:
    """Check collision freedom for a supplied or full legal move set."""
    candidates = list(board.legal_moves if moves is None else moves)
    encoded = [move_to_action(board, move) for move in candidates]
    return len(encoded) == len(set(encoded))

