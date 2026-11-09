from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID
from backend.app.matchmaking.policy import elo_delta


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
        delta = elo_delta(white.value, black.value, outcome, k=self.k_factor)
        white.value += delta
        black.value -= delta
        white.games_count += 1
        black.games_count += 1
        self.processed_games.add(game_id)
        return white, black
