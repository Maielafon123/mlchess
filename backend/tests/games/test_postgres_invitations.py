import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from backend.app.games.invitation_service import InvitationService
from backend.app.infra.models import Game, GameEvent, GamePlayer
from backend.tests.games.test_guest_invitations import command, guest, invite

pytestmark = pytest.mark.skipif(
    not os.environ.get("MLCHESS_TEST_DATABASE_URL"),
    reason="Disposable PostgreSQL URL required",
)


def test_two_guests_race_for_one_seat_and_only_one_commits(pg_app):
    pg_app.state.invitation_service = InvitationService(
        pg_app.state.database_factory,
        secret="x" * 43,
        public_origin="http://testserver",
    )
    with (
        TestClient(pg_app) as creator,
        TestClient(pg_app) as first,
        TestClient(pg_app) as second,
    ):
        owner, h1, h2 = guest(creator), guest(first), guest(second)
        body, token = invite(creator, owner)
        path = f"/api/v1/invitations/{body['invite_id']}/accept"
        with ThreadPoolExecutor(2) as pool:
            futures = [
                pool.submit(
                    http.post, path, json={"token": token}, headers=command(headers)
                )
                for http, headers in [(first, h1), (second, h2)]
            ]
            results = [future.result(timeout=10) for future in futures]
        assert sorted(response.status_code for response in results) == [200, 409]

        async def check():
            async with pg_app.state.database_factory() as session:
                game_id = UUID(body["game_id"])
                game = await session.get(Game, game_id)
                assert game.status == "active" and game.version == 1
                assert (
                    await session.scalar(
                        select(func.count())
                        .select_from(GamePlayer)
                        .where(GamePlayer.game_id == game_id)
                    )
                    == 2
                )
                assert (
                    await session.scalar(
                        select(func.count())
                        .select_from(GameEvent)
                        .where(GameEvent.game_id == game_id)
                    )
                    == 2
                )

        asyncio.run(check())
