from fastapi import FastAPI

from infra.release_check import audit_routes, normalize_path


def test_empty_or_wrong_method_routes_cannot_pass_release_preflight():
    app = FastAPI()

    @app.get("/api/v1/games")
    def games():
        return []

    report = audit_routes(app)
    assert report["status"] == "blocked"
    assert "POST /api/v1/games" in report["missing_http"]
    assert "/ws/v1/games/{game_id}" in report["missing_websockets"]


def test_http_route_does_not_satisfy_websocket_gate():
    app = FastAPI()

    @app.get("/ws/v1/games/{id}")
    def fake_ws(id: str):
        return id

    assert audit_routes(app)["missing_websockets"]

    @app.websocket("/ws/v1/games/{id}")
    async def ws(socket):
        await socket.close()

    assert not audit_routes(app)["missing_websockets"]
    assert normalize_path("/games/{id}/moves") == "/games/{}/moves"
