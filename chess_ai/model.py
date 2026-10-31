"""Compact policy–Q–WDL residual network used for the first vertical slice."""

from __future__ import annotations

from dataclasses import dataclass

import torch
from torch import nn

from .encoding import ACTION_PLANES, ACTION_SIZE, INPUT_PLANES


@dataclass(frozen=True)
class PolicyValueOutput:
    policy_logits: torch.Tensor
    q_value: torch.Tensor
    wdl_logits: torch.Tensor


class ResidualBlock(nn.Module):
    def __init__(self, channels: int) -> None:
        super().__init__()
        self.conv1 = nn.Conv2d(channels, channels, kernel_size=3, padding=1, bias=False)
        self.norm1 = nn.BatchNorm2d(channels)
        self.conv2 = nn.Conv2d(channels, channels, kernel_size=3, padding=1, bias=False)
        self.norm2 = nn.BatchNorm2d(channels)
        self.activation = nn.ReLU(inplace=True)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        residual = x
        x = self.activation(self.norm1(self.conv1(x)))
        x = self.norm2(self.conv2(x))
        return self.activation(x + residual)


class PolicyValueNet(nn.Module):
    """AlphaZero-style CNN with policy, scalar-Q and WDL heads.

    The default 10×128 configuration is intentionally modest for a single
    16 GB GPU. ``width=32, blocks=2`` is useful for CPU/GPU smoke tests.
    """

    def __init__(self, width: int = 128, blocks: int = 10, input_planes: int = INPUT_PLANES) -> None:
        super().__init__()
        if width < 8 or blocks < 1:
            raise ValueError("width must be at least 8 and blocks must be positive")
        self.stem = nn.Sequential(
            nn.Conv2d(input_planes, width, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(width),
            nn.ReLU(inplace=True),
        )
        self.trunk = nn.Sequential(*(ResidualBlock(width) for _ in range(blocks)))

        self.policy_head = nn.Sequential(
            nn.Conv2d(width, 64, kernel_size=1, bias=False),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.Conv2d(64, ACTION_PLANES, kernel_size=1),
        )
        self.value_features = nn.Sequential(
            nn.Conv2d(width, 32, kernel_size=1, bias=False),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
            nn.AdaptiveAvgPool2d(1),
            nn.Flatten(),
        )
        self.q_head = nn.Sequential(nn.Linear(32, 64), nn.ReLU(inplace=True), nn.Linear(64, 1), nn.Tanh())
        self.wdl_head = nn.Sequential(nn.Linear(32, 64), nn.ReLU(inplace=True), nn.Linear(64, 3))

    def forward(self, state: torch.Tensor) -> PolicyValueOutput:
        if state.ndim != 4 or state.shape[1:] != (INPUT_PLANES, 8, 8):
            raise ValueError(f"expected [batch, {INPUT_PLANES}, 8, 8], got {tuple(state.shape)}")
        features = self.trunk(self.stem(state))
        policy_logits = self.policy_head(features).flatten(start_dim=1)
        if policy_logits.shape[1] != ACTION_SIZE:
            raise RuntimeError(f"policy head returned {policy_logits.shape[1]} actions, expected {ACTION_SIZE}")
        value_features = self.value_features(features)
        return PolicyValueOutput(
            policy_logits=policy_logits,
            q_value=self.q_head(value_features).squeeze(-1),
            wdl_logits=self.wdl_head(value_features),
        )


def parameter_count(model: nn.Module) -> int:
    return sum(parameter.numel() for parameter in model.parameters() if parameter.requires_grad)

