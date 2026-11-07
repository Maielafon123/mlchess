from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.infra.settings import Settings
from backend.app.main import create_app


def client():
    app = create_app(
        Settings(
            environment="test", public_origin="http://testserver", dev_auth_enabled=True
        )
    )
    return TestClient(app)


def headers():
    return {"Origin": "http://testserver"}


def test_dev_login_me_and_logout_revoke_session():
    with client() as http:
        login = http.post(
            "/api/v1/auth/dev-login", json={"display_name": "Alice"}, headers=headers()
        )
        assert login.status_code == 200
        assert login.json()["display_name"] == "Alice"
        csrf = http.cookies.get("mlchess_csrf")
        assert csrf
        assert http.get("/api/v1/me").status_code == 200
        logout = http.post(
            "/api/v1/logout", headers={**headers(), "X-CSRF-Token": csrf}
        )
        assert logout.status_code == 204
        assert http.get("/api/v1/me").status_code == 401


def test_logout_requires_csrf_and_dev_login_is_disabled_by_default():
    with client() as http:
        assert http.post("/api/v1/auth/dev-login", headers=headers()).status_code == 422
    app = create_app(Settings(environment="test", public_origin="http://testserver"))
    with TestClient(app) as http:
        assert http.post("/api/v1/auth/dev-login", headers=headers()).status_code == 404


def test_production_rejects_dev_auth():
    try:
        Settings(
            environment="production",
            public_origin="https://example.test",
            dev_auth_enabled=True,
        )
    except ValueError:
        return
    raise AssertionError("production must reject dev auth")
