from __future__ import annotations

import asyncio
import io
import json
import logging
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel, ValidationError

from backend.app.infra.http import RequestLogFormatter, request_id_context
from backend.app.infra.problems import PublicProblem
from backend.app.infra.settings import Settings
from backend.app.main import create_app
from contracts.validate import load_registry, validator


class InputPayload(BaseModel):
    count: int


@pytest.fixture
def settings():
    return Settings(environment="test", public_origin="http://testserver")


@pytest.fixture
def logs():
    output = io.StringIO()
    logger = logging.getLogger("mlchess.test." + str(uuid4()))
    logger.handlers = [logging.StreamHandler(output)]
    logger.handlers[0].setFormatter(RequestLogFormatter())
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger, output


@pytest.fixture(scope="module")
def registry():
    return load_registry()[0]


def assert_problem(response, status, registry):
    assert response.status_code == status
    assert response.headers["content-type"] == "application/problem+json"
    payload = response.json()
    assert payload["status"] == status
    assert payload["request_id"] == response.headers["x-request-id"]
    assert str(UUID(payload["request_id"], version=4)) == payload["request_id"]
    validator(
        "https://mlchess.local/contracts/common/v1.yaml#/$defs/ProblemDetailsV1",
        registry,
    ).validate(payload)
    assert response.headers["cache-control"] == "no-store"
    return payload


def test_liveness_and_lifecycle_readiness(settings, logs, registry):
    app = create_app(settings, logger=logs[0])
    client = TestClient(app)
    assert_problem(client.get("/health/ready"), 503, registry)
    assert client.get("/health/live").json() == {"schema_version": 1, "status": "ok"}
    with client:
        ready = client.get("/health/ready")
        assert ready.status_code == 200
        validator(
            "https://mlchess.local/contracts/common/v1.yaml#/$defs/HealthV1", registry
        ).validate(ready.json())
    assert app.state.started is False


def test_failed_readiness_does_not_disclose_dependency_secrets(
    settings, logs, registry
):
    async def database():
        raise RuntimeError("postgresql://owner:password@private-host/private-db")

    app = create_app(settings, readiness_checks=[database], logger=logs[0])
    with TestClient(app) as client:
        assert_problem(client.get("/health/ready"), 503, registry)
        assert client.get("/health/live").status_code == 200
    assert "password" not in logs[1].getvalue()
    assert "private-host" not in logs[1].getvalue()


def test_readiness_timeout_cancels_probe(settings, logs, registry):
    cancelled = []

    async def stuck():
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.append(True)

    app = create_app(
        settings.model_copy(update={"readiness_timeout_ms": 10}),
        readiness_checks=[stuck],
        logger=logs[0],
    )
    with TestClient(app) as client:
        assert_problem(client.get("/health/ready"), 503, registry)
    assert cancelled == [True]


def test_readiness_cannot_mistake_false_for_success(settings, logs, registry):
    async def failed():
        return False

    with TestClient(
        create_app(settings, readiness_checks=[failed], logger=logs[0])
    ) as client:
        assert_problem(client.get("/health/ready"), 503, registry)


@pytest.mark.parametrize(
    "url", ["/missing", "/docs", "/redoc", "/openapi.json", "/api/v1/games"]
)
def test_missing_and_unimplemented_routes_return_problem(settings, logs, registry, url):
    with TestClient(create_app(settings, logger=logs[0])) as client:
        assert_problem(client.get(url), 404, registry)


def test_method_not_allowed_is_a_contract_error(settings, logs, registry):
    with TestClient(create_app(settings, logger=logs[0])) as client:
        response = client.post("/health/live", headers={"Origin": "http://testserver"})
        assert_problem(response, 405, registry)
        assert "GET" in response.headers["allow"]


@pytest.mark.parametrize("status", [400, 401, 403, 409, 422, 429, 503])
def test_public_errors_use_safe_fixed_messages(settings, logs, registry, status):
    app = create_app(settings, logger=logs[0])

    @app.get("/test/error")
    async def error():
        raise HTTPException(status, detail="private-token-secret")

    with TestClient(app) as client:
        response = client.get("/test/error")
        assert_problem(response, status, registry)
        assert "private-token-secret" not in response.text
    assert "private-token-secret" not in logs[1].getvalue()


def test_unhandled_exception_is_sanitized_even_with_testclient_reraise(
    settings, logs, registry
):
    app = create_app(settings, logger=logs[0])

    @app.get("/test/error")
    async def error():
        raise RuntimeError("secret-key-and-private-stack")

    with TestClient(app, raise_server_exceptions=True) as client:
        response = client.get(
            "/test/error?api_key=query-secret",
            headers={
                "Authorization": "Bearer header-secret",
                "Cookie": "session=cookie-secret",
            },
        )
        assert assert_problem(response, 500, registry)["code"] == "INTERNAL_ERROR"
    combined = response.text + logs[1].getvalue()
    for secret in [
        "secret-key",
        "private-stack",
        "query-secret",
        "header-secret",
        "cookie-secret",
        "Traceback",
    ]:
        assert secret not in combined
    entry = json.loads(logs[1].getvalue().splitlines()[-1])
    assert entry["event"] == "request.failed"
    assert entry["status"] == 500


def test_request_validation_hides_input_and_messages(settings, logs, registry):
    app = create_app(settings, logger=logs[0])

    @app.post("/test/input")
    async def input_body(body: InputPayload):
        return {"count": body.count}

    @app.get("/test/query")
    async def query(count: int):
        return {"count": count}

    with TestClient(app) as client:
        response = client.get("/test/query?count=body-secret")
        assert_problem(response, 422, registry)
        assert "body-secret" not in response.text + logs[1].getvalue()
        response = client.post(
            "/test/input",
            json={"count": "body-secret"},
            headers={"Origin": "http://testserver"},
        )
        assert_problem(response, 422, registry)
        assert "body-secret" not in response.text + logs[1].getvalue()


def test_application_public_problem_is_serialized(settings, logs, registry):
    app = create_app(settings, logger=logs[0])

    @app.get("/test/busy")
    async def busy():
        raise PublicProblem(503)

    with TestClient(app) as client:
        assert_problem(client.get("/test/busy"), 503, registry)


@pytest.mark.parametrize(
    "origin",
    [
        "https://evil.invalid",
        "http://testserver.evil.invalid",
        "null",
        "http://testserver/",
        "http://user:secret@testserver",
        "http://testserver/path",
    ],
)
def test_cross_origin_requests_are_rejected(settings, logs, registry, origin):
    with TestClient(create_app(settings, logger=logs[0])) as client:
        response = client.get("/health/live", headers={"Origin": origin})
        assert_problem(response, 403, registry)
        assert "access-control-allow-origin" not in response.headers
        assert "access-control-allow-credentials" not in response.headers


def test_same_origin_and_originless_read_are_allowed(settings, logs):
    with TestClient(create_app(settings, logger=logs[0])) as client:
        assert client.get("/health/live").status_code == 200
        assert (
            client.get(
                "/health/live", headers={"Origin": "http://testserver"}
            ).status_code
            == 200
        )


def test_unsafe_originless_request_fails_closed(settings, logs, registry):
    with TestClient(create_app(settings, logger=logs[0])) as client:
        assert_problem(client.post("/health/live"), 403, registry)


@pytest.mark.parametrize(
    "host", ["evil.invalid", "testserver.evil.invalid", "user:secret@testserver"]
)
def test_untrusted_host_is_rejected(settings, logs, registry, host):
    with TestClient(create_app(settings, logger=logs[0])) as client:
        assert_problem(
            client.get("/health/live", headers={"Host": host}), 400, registry
        )


def test_duplicate_origin_header_is_rejected(settings, logs, registry):
    with TestClient(create_app(settings, logger=logs[0])) as client:
        assert_problem(
            client.get(
                "/health/live",
                headers=[
                    ("Origin", "http://testserver"),
                    ("Origin", "https://evil.invalid"),
                ],
            ),
            400,
            registry,
        )


def test_untrusted_request_id_is_not_echoed(settings, logs):
    with TestClient(create_app(settings, logger=logs[0])) as client:
        first = client.get(
            "/health/live", headers={"X-Request-ID": "attacker-private-info"}
        )
        second = client.get(
            "/health/live", headers={"X-Request-ID": first.headers["x-request-id"]}
        )
    assert first.headers["x-request-id"] != second.headers["x-request-id"]
    assert "attacker-private-info" not in logs[1].getvalue()
    assert set(json.loads(logs[1].getvalue().splitlines()[0])) == {
        "event",
        "request_id",
        "method",
        "status",
        "duration_ms",
    }


def test_request_context_is_isolated_and_restored(settings, logs):
    app = create_app(settings, logger=logs[0])

    @app.get("/test/context")
    async def context():
        await asyncio.sleep(0)
        return {"request_id": request_id_context.get()}

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            responses = await asyncio.gather(
                *(client.get("/test/context") for _ in range(8))
            )
        assert len({response.json()["request_id"] for response in responses}) == 8
        assert all(
            response.json()["request_id"] == response.headers["x-request-id"]
            for response in responses
        )
        assert request_id_context.get() is None

    asyncio.run(run())


@pytest.mark.parametrize("environment", ["production", "staging"])
@pytest.mark.parametrize(
    "change", [{"dev_auth_enabled": True}, {"public_origin": "http://example.com"}]
)
def test_production_settings_deny_unsafe_auth_and_transport(environment, change):
    changed = dict(change)
    with pytest.raises(ValidationError):
        Settings(
            environment=environment,
            public_origin=changed.pop("public_origin", "https://chess.example.com"),
            **changed,
        )


@pytest.mark.parametrize(
    "origin",
    [
        "*",
        "http://*.example.com",
        "https://user:password@example.com",
        "https://example.com/path",
        "https://example.com?secret=x",
        "https://example.com#x",
        "https://example.com:0",
        "https://example.com:99999",
        "https://example.com\n",
    ],
)
def test_settings_reject_unsafe_origins(origin):
    with pytest.raises(ValidationError):
        Settings(public_origin=origin)


def test_environment_prefix_is_loaded_without_dotenv(monkeypatch):
    monkeypatch.setenv("MLCHESS_ENVIRONMENT", "production")
    monkeypatch.setenv("MLCHESS_PUBLIC_ORIGIN", "https://chess.example.com:443/")
    assert Settings().public_origin == "https://chess.example.com"


def test_large_readiness_registry_is_not_accepted(settings, logs):
    async def okay():
        return None

    with pytest.raises(ValueError, match="bounded"):
        create_app(settings, readiness_checks=[okay] * 9, logger=logs[0])


def test_settings_errors_hide_credential_values():
    with pytest.raises(ValidationError) as exc:
        Settings(public_origin="https://user:startup-secret@example.com")
    assert "startup-secret" not in str(exc.value)
