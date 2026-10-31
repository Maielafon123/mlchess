"""Generate MCTS self-play games and save compact replay shards."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from collections.abc import Callable

import chess
import numpy as np

from .encoding import encode_board
from .mcts import MCTS


@dataclass(frozen=True)
class SelfPlayGame:
    states: list[np.ndarray]
    turns: list[bool]
    policy_actions: list[np.ndarray]
    policy_visits: list[np.ndarray]
    moves: list[str]
    winner: chess.Color | None

    def value_targets(self) -> np.ndarray:
        if self.winner is None:
            return np.zeros(len(self.turns), dtype=np.float32)
        return np.asarray([1.0 if turn == self.winner else -1.0 for turn in self.turns], dtype=np.float32)


def _sample_action(actions: np.ndarray, visits: np.ndarray, temperature: float, rng: np.random.Generator) -> int:
    if temperature <= 0:
        return int(actions[np.argmax(visits)])
    weights = visits.astype(np.float64) ** (1.0 / temperature)
    if not weights.sum():
        weights.fill(1.0)
    return int(rng.choice(actions, p=weights / weights.sum()))


def play_selfplay_game(
    search: MCTS,
    *,
    simulations: int,
    temperature_moves: int = 20,
    max_plies: int = 512,
    seed: int | None = None,
    on_move: Callable[[dict], None] | None = None,
) -> SelfPlayGame:
    """Play one game, using visit counts as the policy training target."""
    if simulations < 2:
        raise ValueError("self-play needs at least 2 simulations")
    board = chess.Board()
    rng = np.random.default_rng(seed)
    states: list[np.ndarray] = []
    turns: list[bool] = []
    policies: list[np.ndarray] = []
    visits_list: list[np.ndarray] = []
    moves: list[str] = []
    for ply in range(max_plies):
        if board.is_game_over(claim_draw=True):
            break
        root = search.search(board, simulations)
        actions = np.fromiter(root.children, dtype=np.int32)
        visits = np.asarray([root.children[int(action)].visit_count for action in actions], dtype=np.int32)
        if not len(actions):
            break
        states.append(encode_board(board))
        turns.append(board.turn)
        policies.append(actions)
        visits_list.append(visits)
        action = _sample_action(actions, visits, 1.0 if ply < temperature_moves else 0.0, rng)
        move = root.moves[action]
        san = board.san(move)
        moves.append(move.uci())
        board.push(move)
        if on_move is not None:
            on_move(
                {
                    "status": "playing",
                    "ply": ply + 1,
                    "fen": board.fen(),
                    "last_move": {"uci": move.uci(), "san": san},
                    "moves": moves.copy(),
                    "root_value": root.value,
                    "legal_moves": len(actions),
                }
            )
    outcome = board.outcome(claim_draw=True)
    if on_move is not None:
        on_move(
            {
                "status": "finished",
                "ply": len(moves),
                "fen": board.fen(),
                "moves": moves,
                "winner": None if outcome is None or outcome.winner is None else ("white" if outcome.winner else "black"),
            }
        )
    return SelfPlayGame(states, turns, policies, visits_list, moves, None if outcome is None else outcome.winner)


def save_selfplay_game(game: SelfPlayGame, path: Path) -> None:
    """Save one game without object arrays, suitable for streaming later."""
    if not game.states:
        raise ValueError("cannot save an empty game")
    path.parent.mkdir(parents=True, exist_ok=True)
    lengths = np.asarray([len(actions) for actions in game.policy_actions], dtype=np.int32)
    offsets = np.concatenate((np.asarray([0], dtype=np.int32), np.cumsum(lengths, dtype=np.int32)))
    np.savez_compressed(
        path,
        states=np.stack(game.states).astype(np.float16),
        turns=np.asarray(game.turns, dtype=np.bool_),
        values=game.value_targets(),
        policy_offsets=offsets,
        policy_actions=np.concatenate(game.policy_actions).astype(np.int16),
        policy_visits=np.concatenate(game.policy_visits).astype(np.int16),
        moves=np.asarray(game.moves),
        winner=-1 if game.winner is None else int(game.winner),
    )
