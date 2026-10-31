from __future__ import annotations

import chess
import torch

from chess_ai.encoding import ACTION_SIZE
from chess_ai.model import PolicyValueNet
from chess_ai.stream import TrainingExample
from chess_ai.encoding import encode_board, legal_action_indices, move_to_action
from chess_ai.training import collate_examples, legal_masked_cross_entropy, policy_value_loss


def make_example() -> TrainingExample:
    board = chess.Board()
    move = chess.Move.from_uci("e2e4")
    action = move_to_action(board, move)
    return TrainingExample(
        state=encode_board(board),
        action=action,
        policy_action=action,
        legal_actions=legal_action_indices(board),
        value_target=0.1,
        wdl_target=1,
        source="fixture",
        game_id="fixture:0",
        ply=0,
        opening=None,
        themes=(),
        rating=None,
    )


def test_model_outputs_and_loss_are_finite() -> None:
    batch = collate_examples([make_example(), make_example()])
    model = PolicyValueNet(width=16, blocks=1)
    output = model(batch.state)
    assert output.policy_logits.shape == (2, ACTION_SIZE)
    assert output.q_value.shape == (2,)
    assert output.wdl_logits.shape == (2, 3)
    loss = policy_value_loss(output, batch)
    assert torch.isfinite(loss.total)
    loss.total.backward()


def test_illegal_logits_do_not_change_masked_policy_loss() -> None:
    batch = collate_examples([make_example()])
    logits = torch.zeros((1, ACTION_SIZE), requires_grad=True)
    baseline = legal_masked_cross_entropy(logits, batch.policy_target, batch.legal_mask)
    altered = logits.detach().clone()
    altered[~batch.legal_mask] = 1000.0
    altered.requires_grad_()
    assert torch.allclose(
        baseline,
        legal_masked_cross_entropy(altered, batch.policy_target, batch.legal_mask),
    )
