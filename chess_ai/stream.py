"""Streaming PGN/Zstandard ingestion with source-aware training records."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
import io
from pathlib import Path
from typing import TextIO

import chess
import chess.pgn
import numpy as np
import zstandard as zstd

from .encoding import encode_board, legal_action_indices, move_to_action


@dataclass(frozen=True)
class ParsedComment:
    q_value: float | None
    best_move: chess.Move | None


@dataclass(frozen=True)
class TrainingExample:
    """One position before a played PGN move.

    ``value_target`` is always from the current player's point of view. A WDL
    target is absent for position-only data such as ChessBench where Result is
    ``*``. Educational metadata is preserved but intentionally does not affect
    the engine loss.
    """

    state: np.ndarray
    action: int
    policy_action: int
    legal_actions: np.ndarray
    value_target: float
    wdl_target: int | None
    source: str
    game_id: str
    ply: int
    opening: str | None
    themes: tuple[str, ...]
    rating: int | None
    # MCTS records a sparse visit-count policy; PGN examples leave these unset.
    policy_actions: np.ndarray | None = None
    policy_weights: np.ndarray | None = None


def parse_comment(comment: str, board: chess.Board) -> ParsedComment:
    """Read a ``q [best_uci]`` annotation without trusting malformed tokens."""
    tokens = comment.split()
    if not tokens:
        return ParsedComment(q_value=None, best_move=None)

    try:
        q_value = float(tokens[0])
    except ValueError:
        return ParsedComment(q_value=None, best_move=None)
    if not -1.0 <= q_value <= 1.0:
        return ParsedComment(q_value=None, best_move=None)

    best_move: chess.Move | None = None
    for token in tokens[1:]:
        try:
            candidate = board.parse_uci(token)
        except ValueError:
            continue
        best_move = candidate
        break
    return ParsedComment(q_value=q_value, best_move=best_move)


@contextmanager
def open_pgn_text(path: str | Path) -> Iterator[TextIO]:
    """Open plain or .zst PGN as text without materialising the whole shard."""
    path = Path(path)
    if path.suffix == ".zst":
        raw = path.open("rb")
        reader = zstd.ZstdDecompressor().stream_reader(raw)
        text = None
        try:
            text = io.TextIOWrapper(reader, encoding="utf-8", errors="replace")
            yield text
        finally:
            if text is not None:
                text.close()
            else:
                reader.close()
                raw.close()
        return

    with path.open("r", encoding="utf-8", errors="replace") as text:
        yield text


def iter_games(path: str | Path, max_games: int | None = None) -> Iterator[chess.pgn.Game]:
    """Yield games lazily from one compressed or ordinary PGN file."""
    with open_pgn_text(path) as text:
        count = 0
        while max_games is None or count < max_games:
            game = chess.pgn.read_game(text)
            if game is None:
                return
            count += 1
            yield game


def game_source(game: chess.pgn.Game) -> str:
    event = game.headers.get("Event", "").casefold()
    if "lc0" in event:
        return "lc0"
    if "chessbench" in event:
        return "chessbench"
    if "puzzle" in event or game.headers.get("Themes"):
        return "puzzle"
    return "other"


def is_standard_game(game: chess.pgn.Game) -> bool:
    """Exclude Chess960 and other variants from the standard-chess v1 stream."""
    variant = game.headers.get("Variant", "standard").casefold().replace(" ", "")
    if variant not in {"standard", "chess"}:
        return False
    try:
        return not game.board().chess960
    except ValueError:
        return False


def _result_from_turn(result: str, turn: chess.Color) -> int | None:
    white_result = {"1-0": 1, "0-1": -1, "1/2-1/2": 0}.get(result)
    if white_result is None:
        return None
    return white_result if turn == chess.WHITE else -white_result


def _parse_rating(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def iter_examples_from_game(
    game: chess.pgn.Game,
    *,
    game_id: str,
    standard_only: bool = True,
) -> Iterator[TrainingExample]:
    """Yield source-aware position records for a single PGN game."""
    if standard_only and not is_standard_game(game):
        return

    try:
        board = game.board()
    except ValueError:
        return

    source = game_source(game)
    result = game.headers.get("Result", "*")
    opening = game.headers.get("Opening") or None
    themes = tuple(theme for theme in (game.headers.get("Themes") or "").split() if theme)
    rating = _parse_rating(game.headers.get("Rating"))

    for ply, node in enumerate(game.mainline()):
        move = node.move
        if move not in board.legal_moves:
            return

        annotation = parse_comment(node.comment, board)
        action = move_to_action(board, move)
        policy_action = move_to_action(board, annotation.best_move) if annotation.best_move else action
        wdl_target = _result_from_turn(result, board.turn)
        value_target = annotation.q_value if annotation.q_value is not None else float(wdl_target or 0)

        yield TrainingExample(
            state=encode_board(board),
            action=action,
            policy_action=policy_action,
            legal_actions=legal_action_indices(board),
            value_target=value_target,
            wdl_target=wdl_target,
            source=source,
            game_id=game_id,
            ply=ply,
            opening=opening,
            themes=themes,
            rating=rating,
        )
        board.push(move)


def iter_examples(
    paths: Sequence[str | Path],
    *,
    max_games_per_file: int | None = None,
    max_examples: int | None = None,
    standard_only: bool = True,
) -> Iterator[TrainingExample]:
    """Stream examples across shards with a global optional sample cap."""
    emitted = 0
    for path in paths:
        path = Path(path)
        for game_index, game in enumerate(iter_games(path, max_games=max_games_per_file)):
            for example in iter_examples_from_game(
                game,
                game_id=f"{path.name}:{game_index}",
                standard_only=standard_only,
            ):
                yield example
                emitted += 1
                if max_examples is not None and emitted >= max_examples:
                    return

