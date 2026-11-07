from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class Outcome(StrEnum):
    WHITE = "white"
    BLACK = "black"
    DRAW = "draw"


@dataclass
class Rating:
    user_id: UUID
    pool: str
    value: int = 1200
    games_count: int = 0


class RatingService:
    def __init__(self, *, k_factor: int = 32) -> None:
        if not 1 <= k_factor <= 100:
            raise ValueError("k factor is outside allowed range")
        self.k_factor = k_factor
        self.ratings: dict[tuple[UUID, str], Rating] = {}
        self.processed_games: set[UUID] = set()

    def settle(
        self,
        *,
        game_id: UUID,
        white_id: UUID,
        black_id: UUID,
        pool: str,
        outcome: Outcome,
    ) -> tuple[Rating, Rating]:
        if game_id in self.processed_games:
            return self.ratings[(white_id, pool)], self.ratings[(black_id, pool)]
        white = self.ratings.setdefault((white_id, pool), Rating(white_id, pool))
        black = self.ratings.setdefault((black_id, pool), Rating(black_id, pool))
        expected_white = 1 / (1 + 10 ** ((black.value - white.value) / 400))
        actual_white = {Outcome.WHITE: 1.0, Outcome.BLACK: 0.0, Outcome.DRAW: 0.5}[
            outcome
        ]
        delta = round(self.k_factor * (actual_white - expected_white))
        white.value += delta
        black.value -= delta
        white.games_count += 1
        black.games_count += 1
        self.processed_games.add(game_id)
        return white, black
