"""Pure clock-policy port; server UTC accounting is implemented by A-019."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, Self

import chess


@dataclass(frozen=True, slots=True)
class FlagFall:
    # None denotes a draw when the opponent cannot mate under the clock policy.
    winner: chess.Color | None


class ClockPolicy(Protocol):
    def before_command(
        self, *, actor: chess.Color, server_now: datetime
    ) -> FlagFall | None:
        """Check a persisted deadline using trusted server UTC, not client clocks."""
        ...

    def after_legal_move(self, *, actor: chess.Color, server_now: datetime) -> Self:
        """Return the next immutable clock state to persist in the same transaction."""
        ...
