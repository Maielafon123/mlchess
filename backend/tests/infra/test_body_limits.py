import asyncio

from fastapi.testclient import TestClient

from backend.app.infra.http import SafeHTTPMiddleware, default_request_logger
from backend.app.infra.settings import Settings
from backend.app.main import create_app


def test_declared_oversized_command_is_sanitized_before_json_parsing():
    with TestClient(
        create_app(Settings(public_origin="http://testserver", environment="test"))
    ) as http:
        response = http.post(
            "/api/v1/auth/guest",
            content=b"x" * 20000,
            headers={"Origin": "http://testserver"},
        )
        assert response.status_code == 422
        assert response.json()["code"] == "VALIDATION_ERROR"
        assert "xxx" not in response.text


def test_chunked_body_cannot_bypass_limit_or_reach_route():
    called = False
    messages = []

    async def route(scope, receive, send):
        nonlocal called
        called = True

    chunks = iter(
        [
            {"type": "http.request", "body": b"a" * 10000, "more_body": True},
            {"type": "http.request", "body": b"b" * 10000, "more_body": False},
        ]
    )

    async def receive():
        return next(chunks)

    async def send(message):
        messages.append(message)

    middleware = SafeHTTPMiddleware(
        route,
        settings=Settings(public_origin="http://testserver"),
        logger=default_request_logger(),
    )
    scope = {
        "type": "http",
        "method": "POST",
        "headers": [(b"host", b"testserver"), (b"origin", b"http://testserver")],
    }
    asyncio.run(middleware(scope, receive, send))
    assert not called
    assert messages[0]["status"] == 422
