"""Real HTTP pairing and rating settlement over a disposable database."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from backend.app.games.durable import DurableGameService
from backend.app.infra.settings import Settings
from backend.app.main import create_app
from backend.tests.games.test_guest_invitations import guest
from backend.tests.games.test_http_games import login
from contracts.validate import validator

ROOT = "/api/v1/matchmaking"
RAPID, BLITZ = "rapid-10+0", "blitz-5+0"


@pytest.fixture
def settings(tmp_path):
    return Settings(
        environment="test",
        dev_auth_enabled=True,
        public_origin="http://testserver",
        database_auto_create=True,
        database_url="sqlite+aiosqlite:///" + (tmp_path / "rated.db").as_posix(),
    )


def command(headers, key=None):
    return {**headers, "Idempotency-Key": key or str(uuid4())}


def join(http, headers, pool=RAPID, key=None, **overrides):
    return http.post(
        ROOT + "/tickets",
        headers=command(headers, key),
        json={"schema_version": 1, "pool": pool, **overrides},
    )


def ticket_path(ticket):
    return ROOT + "/tickets/" + ticket["ticket_id"]


def check(schema, payload):
    validator(
        "https://mlchess.local/contracts/matchmaking/v1.yaml#/$defs/" + schema
    ).validate(payload)


def paired(first, second, h1, h2):
    one, two = join(first, h1), join(second, h2)
    assert one.status_code == two.status_code == 201, (one.text, two.text)
    matched = two.json()
    assert matched["status"] == "matched" and matched["game_id"]
    check("MatchTicketV1", matched)
    assert first.get(ticket_path(one.json())).json()["game_id"] == matched["game_id"]
    return "/api/v1/games/" + matched["game_id"]


def test_rated_match_move_resign_receipts_and_restart(settings):
    app = create_app(settings)
    with (
        TestClient(app) as first,
        TestClient(app) as second,
        TestClient(app) as stranger,
    ):
        h1, h2 = login(first, "Rated first"), login(second, "Rated second")
        login(stranger, "Stranger")
        key = str(uuid4())
        original = join(first, h1, key=key)
        assert original.status_code == 201, original.text
        check("MatchTicketV1", original.json())
        assert original.json()["status"] == "searching"
        assert join(first, h1).json() == original.json()
        assert join(first, h1, BLITZ, key).status_code == 409
        assert join(first, h1, BLITZ).status_code == 409
        assert stranger.get(ticket_path(original.json())).status_code == 403
        result = join(second, h2)
        assert result.status_code == 201, result.text
        game_id = result.json()["game_id"]
        assert (
            game_id
            and first.get(ticket_path(original.json())).json()["game_id"] == game_id
        )
        assert join(first, h1, key=key).json() == original.json()
        assert join(first, h1).json()["game_id"] == game_id
        assert first.get(ROOT + "/current").json()["ticket"]["game_id"] == game_id
        assert (
            first.delete(ticket_path(original.json()), headers=command(h1)).status_code
            == 409
        )
        path = "/api/v1/games/" + game_id
        assert (
            stranger.get(path).status_code
            == stranger.get(path + "/rating").status_code
            == 403
        )
        r1, r2 = (c.get(path + "/rating").json() for c in (first, second))
        check("RatedGameV1", r1)
        assert r1["side"] != r2["side"] and r1["rating_change"] is None
        white, black, hw, hb = (
            (first, second, h1, h2)
            if r1["side"] == "white"
            else (second, first, h2, h1)
        )
        game = white.get(path).json()
        assert game["mode"] == "rated" and game["clock"]["running_side"] == "white"
        assert game["capabilities"] == {
            "can_move": True,
            "can_takeback": False,
            "can_analyze_now": False,
        }
        assert len({player["user_id"] for player in game["players"]}) == 2
        moved = white.post(
            path + "/moves",
            headers=hw,
            json={"client_move_id": str(uuid4()), "expected_version": 0, "uci": "e2e4"},
        )
        assert moved.status_code == 200, moved.text
        assert black.get(path).json()["moves"][0]["uci"] == "e2e4"
        assert (
            white.post(
                path + "/analysis-requests",
                headers=command(hw),
                json={"ply": 1, "analysis_level": "quick"},
            ).status_code
            == 403
        )
        assert black.get(path + "/analysis/1").status_code == 403
        assert (
            white.post(
                path + "/takeback",
                headers=hw,
                json={
                    "client_action_id": str(uuid4()),
                    "expected_version": 1,
                    "plies": 1,
                },
            ).status_code
            == 403
        )
        resign_headers = command(hb)
        ended = black.post(
            path + "/resign", headers=resign_headers, json={"expected_version": 1}
        )
        assert ended.status_code == 200 and ended.json()["result"] == "white", (
            ended.text
        )
        assert (
            black.post(
                path + "/resign", headers=resign_headers, json={"expected_version": 1}
            ).json()
            == ended.json()
        )
        assert (
            black.post(
                path + "/resign", headers=command(hb), json={"expected_version": 2}
            ).status_code
            == 409
        )
        win, loss = (
            white.get(path + "/rating").json(),
            black.get(path + "/rating").json(),
        )
        check("RatedGameV1", win)
        assert (
            win["rating_change"]["after"] == 1216
            and loss["rating_change"]["after"] == 1184
        )
        assert (
            win["rating_change"]["games_count"]
            == loss["rating_change"]["games_count"]
            == 1
        )
        assert white.get(ROOT + "/current").json()["ticket"] is None
        assert (
            next(
                p
                for p in white.get(ROOT + "/pools").json()["items"]
                if p["pool"] == RAPID
            )["your_rating"]
            == 1216
        )
        cookies = dict(white.cookies)
    with TestClient(create_app(settings)) as restarted:
        restarted.cookies.update(cookies)
        assert restarted.get(path + "/rating").json() == win
        assert restarted.get(path).json()["termination"] == "resignation"


def test_cancel_pool_isolation_and_ttl(settings, monkeypatch):
    now = [datetime(2026, 1, 1, tzinfo=timezone.utc)]

    async def clock(_session):
        return now[0]

    monkeypatch.setattr(DurableGameService, "now", staticmethod(clock))
    app = create_app(settings)
    with TestClient(app) as first, TestClient(app) as second:
        h1, h2 = login(first, "Cancel"), login(second, "Expire")
        a, b = join(first, h1, BLITZ).json(), join(second, h2, RAPID).json()
        assert a["status"] == b["status"] == "searching"
        assert second.delete(ticket_path(a), headers=command(h2)).status_code == 403
        assert (
            first.delete(
                ticket_path(a), headers={"Origin": "http://testserver"}
            ).status_code
            == 403
        )
        cancellation = command(h1)
        cancelled = first.delete(ticket_path(a), headers=cancellation)
        assert (
            cancelled.status_code == 200 and cancelled.json()["status"] == "cancelled"
        )
        assert (
            first.delete(ticket_path(a), headers=cancellation).json()
            == cancelled.json()
        )
        now[0] += timedelta(seconds=120)
        assert second.get(ticket_path(b)).json()["status"] == "expired"
        assert second.get(ROOT + "/current").json()["ticket"] is None
        renewed = join(second, h2, BLITZ)
        assert renewed.status_code == 201, renewed.text
        assert (
            renewed.json()["ticket_id"] != b["ticket_id"]
            and renewed.json()["status"] == "searching"
        )


def test_guest_and_forged_queue_parameters_are_denied(settings):
    with TestClient(create_app(settings)) as http:
        assert http.get(ROOT + "/pools").status_code == 401
        headers = guest(http)
        assert all(
            item["your_rating"] is None
            for item in http.get(ROOT + "/pools").json()["items"]
        )
        assert join(http, headers).status_code == 403
        assert http.get(ROOT + "/current").status_code == 403
        headers = login(http)
        assert join(http, headers, "unknown").status_code == 422
        assert join(http, headers, schema_version=True).status_code == 422
        assert join(http, headers, rating=4000).status_code == 422
        assert (
            http.post(
                "/api/v1/games",
                headers=command(headers),
                json={"mode": "rated", "time_control": None},
            ).status_code
            == 422
        )


def test_draw_actions_and_zero_sum_settlement(settings):
    app = create_app(settings)
    with TestClient(app) as first, TestClient(app) as second:
        h1, h2 = login(first, "Offer"), login(second, "Accept")
        path = paired(first, second, h1, h2)
        initial = first.get(path + "/actions").json()
        check("GameActionsV1", initial)
        assert initial["can_offer_draw"] and not initial["can_claim_draw"]
        offer = first.post(
            path + "/draw-offers", headers=command(h1), json={"expected_version": 0}
        )
        assert offer.status_code == 200 and offer.json()["version"] == 1
        assert not first.get(path + "/actions").json()["can_accept_draw"]
        assert second.get(path + "/actions").json()["can_accept_draw"]
        assert (
            first.post(
                path + "/draw-offers/accept",
                headers=command(h1),
                json={"expected_version": 1},
            ).status_code
            == 409
        )
        drawn = second.post(
            path + "/draw-offers/accept",
            headers=command(h2),
            json={"expected_version": 1},
        )
        assert drawn.status_code == 200 and drawn.json()["result"] == "draw", drawn.text
        assert drawn.json()["termination"] == "draw_agreement"
        for client in (first, second):
            change = client.get(path + "/rating").json()["rating_change"]
            assert change["delta"] == 0 and change["games_count"] == 1
