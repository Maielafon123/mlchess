"""Batch construction and losses shared by smoke and main training loops."""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Sequence

import numpy as np
import torch
from torch.nn import functional as F

from .encoding import ACTION_SIZE
from .model import PolicyValueOutput
from .stream import TrainingExample

WDL_IGNORE_INDEX = -100


@dataclass(frozen=True)
class TrainingBatch:
    state: torch.Tensor
    policy_target: torch.Tensor
    policy_distribution: torch.Tensor
    legal_mask: torch.Tensor
    q_target: torch.Tensor
    wdl_target: torch.Tensor

    def to(self, device: torch.device | str) -> "TrainingBatch":
        return TrainingBatch(
            state=self.state.to(device, non_blocking=True),
            policy_target=self.policy_target.to(device, non_blocking=True),
            policy_distribution=self.policy_distribution.to(device, non_blocking=True),
            legal_mask=self.legal_mask.to(device, non_blocking=True),
            q_target=self.q_target.to(device, non_blocking=True),
            wdl_target=self.wdl_target.to(device, non_blocking=True),
        )


@dataclass(frozen=True)
class LossBreakdown:
    total: torch.Tensor
    policy: torch.Tensor
    q_value: torch.Tensor
    wdl: torch.Tensor


def collate_examples(examples: Sequence[TrainingExample]) -> TrainingBatch:
    if not examples:
        raise ValueError("cannot collate an empty batch")
    state = torch.from_numpy(np.stack([example.state for example in examples]))
    policy_target = torch.tensor([example.policy_action for example in examples], dtype=torch.long)
    policy_distribution = torch.zeros((len(examples), ACTION_SIZE), dtype=torch.float32)
    q_target = torch.tensor([example.value_target for example in examples], dtype=torch.float32)
    wdl_target = torch.tensor(
        [WDL_IGNORE_INDEX if example.wdl_target is None else example.wdl_target + 1 for example in examples],
        dtype=torch.long,
    )
    legal_mask = torch.zeros((len(examples), ACTION_SIZE), dtype=torch.bool)
    for index, example in enumerate(examples):
        legal_mask[index, torch.from_numpy(example.legal_actions.astype("int64", copy=False))] = True
        if example.policy_actions is None or example.policy_weights is None:
            policy_distribution[index, example.policy_action] = 1.0
        else:
            actions = torch.from_numpy(example.policy_actions.astype("int64", copy=False))
            weights = torch.from_numpy(example.policy_weights.astype("float32", copy=False))
            if len(actions) != len(weights) or len(actions) == 0 or torch.any(weights < 0) or weights.sum() <= 0:
                raise ValueError("invalid sparse policy target")
            policy_distribution[index, actions] = weights / weights.sum()
    if not torch.all(legal_mask.gather(1, policy_target[:, None])):
        raise ValueError("policy target must always be legal")
    return TrainingBatch(state=state, policy_target=policy_target, policy_distribution=policy_distribution, legal_mask=legal_mask, q_target=q_target, wdl_target=wdl_target)


def legal_masked_cross_entropy(logits: torch.Tensor, targets: torch.Tensor, legal_mask: torch.Tensor) -> torch.Tensor:
    """Cross-entropy where impossible chess moves receive no probability mass."""
    if logits.shape != legal_mask.shape:
        raise ValueError(f"logits shape {tuple(logits.shape)} differs from legal mask {tuple(legal_mask.shape)}")
    masked_logits = logits.masked_fill(~legal_mask, torch.finfo(logits.dtype).min)
    return F.cross_entropy(masked_logits, targets)


def legal_masked_soft_cross_entropy(logits: torch.Tensor, targets: torch.Tensor, legal_mask: torch.Tensor) -> torch.Tensor:
    """Cross-entropy for a normalized MCTS visit-count policy."""
    masked_logits = logits.masked_fill(~legal_mask, torch.finfo(logits.dtype).min)
    return -(targets * F.log_softmax(masked_logits, dim=1)).sum(dim=1).mean()


def policy_value_loss(
    output: PolicyValueOutput,
    batch: TrainingBatch,
    *,
    q_weight: float = 0.5,
    wdl_weight: float = 0.2,
) -> LossBreakdown:
    policy = legal_masked_soft_cross_entropy(output.policy_logits, batch.policy_distribution, batch.legal_mask)
    q_value = F.smooth_l1_loss(output.q_value, batch.q_target)
    has_wdl = batch.wdl_target != WDL_IGNORE_INDEX
    wdl = (
        F.cross_entropy(output.wdl_logits[has_wdl], batch.wdl_target[has_wdl])
        if torch.any(has_wdl)
        else output.wdl_logits.sum() * 0.0
    )
    total = policy + q_weight * q_value + wdl_weight * wdl
    return LossBreakdown(total=total, policy=policy, q_value=q_value, wdl=wdl)

