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


@dataclass(frozen=True, slots=True)
class ServerClock:
    white_remaining_ms: int
    black_remaining_ms: int
    increment_ms: int = 0
    running_side: chess.Color | None = None
    anchor: datetime | None = None

    def __post_init__(self) -> None:
        if min(self.white_remaining_ms, self.black_remaining_ms, self.increment_ms) < 0:
            raise ValueError("clock values cannot be negative")
        if self.running_side is not None and self.anchor is None:
            raise ValueError("running clock requires a UTC anchor")

    def remaining(self, side: chess.Color, *, now: datetime) -> int:
        base = self.white_remaining_ms if side else self.black_remaining_ms
        if self.running_side != side or self.anchor is None:
            return base
        elapsed = max(0, int((now - self.anchor).total_seconds() * 1000))
        return max(0, base - elapsed)

    def before_command(
        self, *, actor: chess.Color, server_now: datetime
    ) -> FlagFall | None:
        if self.remaining(actor, now=server_now) > 0:
            return None
        opponent = not actor
        return FlagFall(
            opponent if self.remaining(opponent, now=server_now) > 0 else None
        )

    def after_legal_move(
        self, *, actor: chess.Color, server_now: datetime
    ) -> ServerClock:
        if self.running_side != actor:
            raise ValueError("clock actor is not the running side")
        white = self.remaining(chess.WHITE, now=server_now)
        black = self.remaining(chess.BLACK, now=server_now)
        if actor:
            white += self.increment_ms
        else:
            black += self.increment_ms
        return ServerClock(white, black, self.increment_ms, not actor, server_now)
