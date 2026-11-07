from __future__ import annotations

import asyncio
import sys
from uuid import uuid4

import pytest
from backend.app.games.domain import NotYourTurn, StaleVersion
from backend.app.games.service import (
    ForbiddenGameActor,
    IdempotencyConflict,
    InMemoryGameCommandService,
)

pytestmark = pytest.mark.skipif(
    sys.platform == "win32",
    reason="The restricted Windows runner cannot create asyncio self-pipes",
)


def test_move_is_idempotent_and_replays_exact_response():
    service = InMemoryGameCommandService()
    white, black = uuid4(), uuid4()
    game_id = service.create_game(mode="friend", white_player=white, black_player=black)
    client_move_id = uuid4()
    first = asyncio.run(
        service.submit_move(
            game_id,
            actor_id=white,
            client_move_id=client_move_id,
            uci="e2e4",
            expected_version=0,
        )
    )
    retry = asyncio.run(
        service.submit_move(
            game_id,
            actor_id=white,
            client_move_id=client_move_id,
            uci="e2e4",
            expected_version=0,
        )
    )
    assert retry is first
    assert service.snapshot(game_id).version == 1

    with pytest.raises(IdempotencyConflict):
        asyncio.run(
            service.submit_move(
                game_id,
                actor_id=white,
                client_move_id=client_move_id,
                uci="d2d4",
                expected_version=0,
            )
        )


def test_stale_turn_and_foreign_actor_are_rejected():
    service = InMemoryGameCommandService()
    white, black, stranger = uuid4(), uuid4(), uuid4()
    game_id = service.create_game(mode="friend", white_player=white, black_player=black)
    with pytest.raises(NotYourTurn):
        asyncio.run(
            service.submit_move(
                game_id,
                actor_id=black,
                client_move_id=uuid4(),
                uci="e7e5",
                expected_version=0,
            )
        )
    with pytest.raises(ForbiddenGameActor):
        asyncio.run(
            service.submit_move(
                game_id,
                actor_id=stranger,
                client_move_id=uuid4(),
                uci="e2e4",
                expected_version=0,
            )
        )
    asyncio.run(
        service.submit_move(
            game_id,
            actor_id=white,
            client_move_id=uuid4(),
            uci="e2e4",
            expected_version=0,
        )
    )
    with pytest.raises(StaleVersion):
        asyncio.run(
            service.submit_move(
                game_id,
                actor_id=black,
                client_move_id=uuid4(),
                uci="e7e5",
                expected_version=0,
            )
        )
