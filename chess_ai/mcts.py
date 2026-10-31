"""Policy-guided Monte-Carlo tree search for standard chess.

Values are always stored from the side-to-move's perspective at each node.
That convention keeps backpropagation explicit: the sign flips once per ply.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import sqrt
from typing import Callable

import chess
import numpy as np
import torch

from .encoding import encode_board, legal_action_indices
from .model import PolicyValueNet


@dataclass
class SearchNode:
    board: chess.Board
    prior: float = 1.0
    visit_count: int = 0
    value_sum: float = 0.0
    children: dict[int, "SearchNode"] = field(default_factory=dict)
    moves: dict[int, chess.Move] = field(default_factory=dict)
    expanded: bool = False

    @property
    def value(self) -> float:
        return self.value_sum / self.visit_count if self.visit_count else 0.0


def terminal_value(board: chess.Board) -> float | None:
    """Return game result from ``board.turn`` perspective, or ``None``."""
    outcome = board.outcome(claim_draw=True)
    if outcome is None:
        return None
    if outcome.winner is None:
        return 0.0
    return 1.0 if outcome.winner == board.turn else -1.0


@torch.no_grad()
def evaluate_position(model: PolicyValueNet, board: chess.Board, device: torch.device) -> tuple[np.ndarray, np.ndarray, float]:
    """Evaluate one non-terminal board and return legal actions and priors."""
    actions = legal_action_indices(board).astype(np.int64, copy=False)
    if not len(actions):
        raise ValueError("cannot evaluate a position without legal moves")
    state = torch.from_numpy(encode_board(board)).unsqueeze(0).to(device)
    model.eval()
    output = model(state)
    logits = output.policy_logits[0, torch.from_numpy(actions).to(device)].float()
    priors = torch.softmax(logits, dim=0).cpu().numpy()
    return actions, priors, float(output.q_value[0].float().cpu())


class MCTS:
    """PUCT search driven by a policy/value network.

    This deliberately uses one inference per leaf for correctness and a small
    surface area. Batched leaf evaluation is the next performance milestone.
    """

    def __init__(
        self,
        model: PolicyValueNet,
        device: torch.device | str,
        *,
        c_puct: float = 1.5,
        evaluator: Callable[[PolicyValueNet, chess.Board, torch.device], tuple[np.ndarray, np.ndarray, float]] = evaluate_position,
    ) -> None:
        if c_puct <= 0:
            raise ValueError("c_puct must be positive")
        self.model = model
        self.device = torch.device(device)
        self.c_puct = c_puct
        self.evaluator = evaluator

    def _expand(self, node: SearchNode) -> float:
        value = terminal_value(node.board)
        if value is not None:
            node.expanded = True
            return value
        actions, priors, value = self.evaluator(self.model, node.board, self.device)
        legal_moves = list(node.board.legal_moves)
        action_to_move = {int(action): move for action, move in zip(legal_action_indices(node.board), legal_moves, strict=True)}
        for action, prior in zip(actions.tolist(), priors.tolist(), strict=True):
            move = action_to_move[int(action)]
            child_board = node.board.copy(stack=False)
            child_board.push(move)
            node.moves[action] = move
            node.children[action] = SearchNode(board=child_board, prior=prior)
        node.expanded = True
        return value

    def _select_child(self, node: SearchNode) -> tuple[int, SearchNode]:
        scale = sqrt(node.visit_count + 1)
        return max(
            node.children.items(),
            key=lambda item: -item[1].value + self.c_puct * item[1].prior * scale / (1 + item[1].visit_count),
        )

    @staticmethod
    def _backpropagate(path: list[SearchNode], value: float) -> None:
        for node in reversed(path):
            node.visit_count += 1
            node.value_sum += value
            value = -value

    def search(self, board: chess.Board, simulations: int) -> SearchNode:
        if simulations < 1:
            raise ValueError("simulations must be positive")
        root = SearchNode(board=board.copy(stack=True))
        for _ in range(simulations):
            node = root
            path = [node]
            while node.expanded and node.children:
                _, node = self._select_child(node)
                path.append(node)
            value = self._expand(node)
            self._backpropagate(path, value)
        return root

    def choose_move(self, board: chess.Board, simulations: int, temperature: float = 0.0) -> chess.Move:
        root = self.search(board, simulations)
        if not root.children:
            raise ValueError("game is already over")
        actions = np.fromiter(root.children, dtype=np.int64)
        visits = np.asarray([root.children[action].visit_count for action in actions], dtype=np.float64)
        if temperature <= 0:
            action = int(actions[np.argmax(visits)])
        else:
            weights = visits ** (1.0 / temperature)
            action = int(np.random.default_rng().choice(actions, p=weights / weights.sum()))
        return root.moves[action]
