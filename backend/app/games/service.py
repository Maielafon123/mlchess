"""Transactional command boundary around the immutable chess domain.

The in-memory repository is deterministic test infrastructure.  Its interface is
deliberately narrow so the PostgreSQL adapter can replace it without moving rule
checks into HTTP handlers.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from uuid import UUID, uuid4

import chess

from .domain import GameDomain, GameError, Mode, MoveRecord, NotYourTurn, StaleVersion


class IdempotencyConflict(GameError):
    pass


class ForbiddenGameActor(GameError):
    pass


@dataclass(frozen=True, slots=True)
class AcceptedMove:
    client_move_id: UUID
    game_id: UUID
    actor_id: UUID
    move: MoveRecord
    snapshot: GameDomain


@dataclass
class _GameEntry:
    game: GameDomain
    players: dict[UUID, chess.Color]
    idempotency: dict[tuple[UUID, UUID], tuple[str, int, AcceptedMove]] = field(
        default_factory=dict
    )
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class InMemoryGameCommandService:
    """Concurrency-safe command service used until the DB repository is wired."""

    def __init__(self) -> None:
        self._games: dict[UUID, _GameEntry] = {}

    def create_game(
        self,
        *,
        mode: Mode,
        white_player: UUID,
        black_player: UUID | None = None,
    ) -> UUID:
        game_id = uuid4()
        players = {white_player: chess.WHITE}
        if black_player is not None:
            players[black_player] = chess.BLACK
        self._games[game_id] = _GameEntry(GameDomain.start(mode), players)
        return game_id

    def snapshot(self, game_id: UUID) -> GameDomain:
        return self._games[game_id].game

    async def submit_move(
        self,
        game_id: UUID,
        *,
        actor_id: UUID,
        client_move_id: UUID,
        uci: str,
        expected_version: int,
    ) -> AcceptedMove:
        entry = self._games[game_id]
        async with entry.lock:
            key = (actor_id, client_move_id)
            prior = entry.idempotency.get(key)
            if prior is not None:
                prior_uci, prior_version, accepted = prior
                if prior_uci != uci or prior_version != expected_version:
                    raise IdempotencyConflict(
                        "client_move_id was reused with another payload"
                    )
                return accepted

            actor = entry.players.get(actor_id)
            if actor is None:
                raise ForbiddenGameActor("actor is not a player in this game")
            if expected_version != entry.game.version:
                raise StaleVersion("game version is stale")
            if actor != entry.game.side_to_move:
                raise NotYourTurn("actor is not on move")
            updated = entry.game.play(
                actor=actor, uci=uci, expected_version=expected_version
            )
            accepted = AcceptedMove(
                client_move_id=client_move_id,
                game_id=game_id,
                actor_id=actor_id,
                move=updated.moves[-1],
                snapshot=updated,
            )
            entry.game = updated
            entry.idempotency[key] = (uci, expected_version, accepted)
            return accepted
