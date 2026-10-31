"""Model evaluation metrics shared by training and future arena tooling."""

from __future__ import annotations

from dataclasses import dataclass

import torch

from .model import PolicyValueNet
from .training import TrainingBatch, WDL_IGNORE_INDEX, policy_value_loss


@dataclass(frozen=True)
class EvaluationMetrics:
    examples: int
    loss: float
    policy_loss: float
    q_loss: float
    wdl_loss: float
    policy_top1: float
    q_mae: float
    wdl_accuracy: float | None


@torch.no_grad()
def evaluate_batches(
    model: PolicyValueNet,
    batches: list[TrainingBatch] | object,
    *,
    device: torch.device,
    amp: bool = True,
) -> EvaluationMetrics:
    """Evaluate a finite iterable of already-collated batches."""
    model.eval()
    totals = {"examples": 0, "loss": 0.0, "policy": 0.0, "q": 0.0, "wdl": 0.0, "top1": 0, "q_abs": 0.0, "wdl_correct": 0, "wdl_count": 0}
    for batch in batches:  # type: ignore[union-attr]
        batch = batch.to(device)
        with torch.autocast(device_type=device.type, dtype=torch.bfloat16, enabled=amp and device.type == "cuda"):
            output = model(batch.state)
            loss = policy_value_loss(output, batch)
            masked_logits = output.policy_logits.masked_fill(~batch.legal_mask, torch.finfo(output.policy_logits.dtype).min)
        count = batch.state.shape[0]
        totals["examples"] += count
        totals["loss"] += loss.total.item() * count
        totals["policy"] += loss.policy.item() * count
        totals["q"] += loss.q_value.item() * count
        totals["wdl"] += loss.wdl.item() * count
        totals["top1"] += (masked_logits.argmax(dim=1) == batch.policy_target).sum().item()
        totals["q_abs"] += (output.q_value.float() - batch.q_target).abs().sum().item()
        known_wdl = batch.wdl_target != WDL_IGNORE_INDEX
        totals["wdl_count"] += known_wdl.sum().item()
        if torch.any(known_wdl):
            totals["wdl_correct"] += (output.wdl_logits[known_wdl].argmax(dim=1) == batch.wdl_target[known_wdl]).sum().item()

    if not totals["examples"]:
        raise ValueError("evaluation received no batches")
    count = totals["examples"]
    return EvaluationMetrics(
        examples=count,
        loss=totals["loss"] / count,
        policy_loss=totals["policy"] / count,
        q_loss=totals["q"] / count,
        wdl_loss=totals["wdl"] / count,
        policy_top1=totals["top1"] / count,
        q_mae=totals["q_abs"] / count,
        wdl_accuracy=(totals["wdl_correct"] / totals["wdl_count"]) if totals["wdl_count"] else None,
    )

