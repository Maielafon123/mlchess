from __future__ import annotations

import hashlib
from dataclasses import dataclass

import chess

from backend.app.games.domain import GameDomain, MoveRecord


class AnalysisError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class PositionSlice:
    ply: int
    before: chess.Board
    after: chess.Board
    move: MoveRecord
    position_key: str


def position_key(before_fen: str, played_move_uci: str) -> str:
    return hashlib.sha256(f"{before_fen}|{played_move_uci}".encode("ascii")).hexdigest()


def reconstruct_position(game: GameDomain, ply: int) -> PositionSlice:
    if type(ply) is not int or not 1 <= ply <= len(game.moves):
        raise AnalysisError("Requested ply is outside the persisted game history")
    board = chess.Board(game.initial_fen)
    for item in game.moves[: ply - 1]:
        board.push_uci(item.uci)
    before = board.copy(stack=True)
    move = game.moves[ply - 1]
    board.push_uci(move.uci)
    return PositionSlice(ply, before, board, move, position_key(before.fen(), move.uci))


def quality_from_cp_loss(cp_loss: int | None, *, mate: bool = False) -> str:
    if mate or cp_loss is None:
        return "unclassified"
    if cp_loss <= 20:
        return "best"
    if cp_loss <= 60:
        return "good"
    if cp_loss <= 150:
        return "inaccuracy"
    if cp_loss <= 300:
        return "mistake"
    return "blunder"
