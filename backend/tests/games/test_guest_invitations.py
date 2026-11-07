import asyncio
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlsplit
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select, update

from backend.app.infra.models import CommandReceipt, Invitation
from backend.app.infra.settings import Settings
from backend.app.main import create_app
from contracts.validate import validator

ORIGIN = {"Origin": "http://testserver"}


def guest(http):
    response = http.post("/api/v1/auth/guest", json={}, headers=ORIGIN)
    assert response.status_code == 200, response.text
    assert response.json()["kind"] == "guest"
    return {**ORIGIN, "X-CSRF-Token": http.cookies["mlchess_csrf"]}


def command(headers):
    return {**headers, "Idempotency-Key": str(uuid4())}


def invite(http, headers):
    response = http.post(
        "/api/v1/games",
        json={"mode": "friend", "time_control": None},
        headers=command(headers),
    )
    assert response.status_code == 201, response.text
    game_id = response.json()["id"]
    create_headers = command(headers)
    response = http.post(
        "/api/v1/invitations", json={"game_id": game_id}, headers=create_headers
    )
    assert response.status_code == 201, response.text
    body = response.json()
    validator(
        "https://mlchess.local/contracts/invitations/v1.yaml#/$defs/InviteSnapshotV1"
    ).validate(body)
    assert (
        http.post(
            "/api/v1/invitations", json={"game_id": game_id}, headers=create_headers
        ).json()
        == body
    )
    token = parse_qs(urlsplit(body["invite_url"]).fragment)["token"][0]
    return body, token


@pytest.fixture
def app(tmp_path):
    return create_app(
        Settings(
            environment="test",
            public_origin="http://testserver",
            database_url="sqlite+aiosqlite:///" + (tmp_path / "guest.db").as_posix(),
            database_auto_create=True,
            invitation_secret="x" * 43,
        )
    )


def test_guest_link_two_users_exact_retries_moves_and_restart(app):
    with TestClient(app) as first, TestClient(app) as second, TestClient(app) as third:
        h1, h2, h3 = guest(first), guest(second), guest(third)
        first_id = first.get("/api/v1/me").json()["id"]
        assert first_id != second.get("/api/v1/me").json()["id"]
        assert (
            first.post("/api/v1/auth/guest", json={}, headers=ORIGIN).json()["id"]
            == first_id
        )
        body, token = invite(first, h1)
        path = f"/api/v1/invitations/{body['invite_id']}/accept"
        assert second.get(f"/api/v1/invitations/{body['invite_id']}").status_code == 403
        assert (
            first.post(path, json={"token": token}, headers=command(h1)).status_code
            == 403
        )
        assert (
            second.post(path, json={"token": token}, headers=ORIGIN).status_code == 403
        )
        accepted_headers = command(h2)
        accepted = second.post(path, json={"token": token}, headers=accepted_headers)
        assert accepted.status_code == 200, accepted.text
        assert accepted.json()["invite_url"] is None
        assert accepted.json()["state"] == "active"
        assert (
            second.post(path, json={"token": token}, headers=accepted_headers).json()
            == accepted.json()
        )
        assert (
            third.post(path, json={"token": token}, headers=command(h3)).status_code
            == 409
        )
        assert third.get(f"/api/v1/games/{body['game_id']}").status_code == 403
        snapshot = first.get(f"/api/v1/games/{body['game_id']}").json()
        assert snapshot["status"] == "active" and snapshot["version"] == 1
        for http, headers, uci in [(first, h1, "e2e4"), (second, h2, "e7e5")]:
            response = http.post(
                f"/api/v1/games/{body['game_id']}/moves",
                json={
                    "uci": uci,
                    "client_move_id": str(uuid4()),
                    "expected_version": snapshot["version"],
                },
                headers=headers,
            )
            assert response.status_code == 200, response.text
            snapshot = response.json()["snapshot"]
        assert snapshot["ply"] == 2
        assert not snapshot["capabilities"]["can_takeback"]
        assert not snapshot["capabilities"]["can_analyze_now"]
        cookies = dict(second.cookies)

        async def check_private_storage():
            async with app.state.database_factory() as session:
                row = await session.get(Invitation, UUID(body["invite_id"]))
                assert row.invite_code_hash != token
                receipts = list(await session.scalars(select(CommandReceipt)))
                assert all(token not in str(receipt.response) for receipt in receipts)

        asyncio.run(check_private_storage())
    with TestClient(create_app(app.state.settings)) as restarted:
        restarted.cookies.update(cookies)
        restored = restarted.get(f"/api/v1/games/{body['game_id']}")
        assert restored.status_code == 200
        assert restored.json()["moves"] == snapshot["moves"]


def test_expired_invalid_token_and_mutation_origin_are_rejected(app):
    with TestClient(app) as first, TestClient(app) as second:
        assert first.post("/api/v1/auth/guest", json={}).status_code == 403
        assert (
            first.post(
                "/api/v1/auth/guest", json={}, headers={"Origin": "http://evil.test"}
            ).status_code
            == 403
        )
        h1, h2 = guest(first), guest(second)
        body, token = invite(first, h1)
        path = f"/api/v1/invitations/{body['invite_id']}/accept"
        assert (
            second.post(path, json={"token": "z" * 43}, headers=command(h2)).status_code
            == 403
        )
        assert (
            second.post(path, json={"token": "bad"}, headers=command(h2)).status_code
            == 422
        )

        async def expire():
            async with app.state.database_factory() as session, session.begin():
                await session.execute(
                    update(Invitation)
                    .where(Invitation.id == UUID(body["invite_id"]))
                    .values(
                        expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)
                    )
                )

        asyncio.run(expire())
        assert (
            first.get(f"/api/v1/invitations/{body['invite_id']}").json()["state"]
            == "expired"
        )
        assert (
            second.post(path, json={"token": token}, headers=command(h2)).status_code
            == 409
        )
        assert (
            first.get(f"/api/v1/games/{body['game_id']}").json()["status"] == "waiting"
        )
