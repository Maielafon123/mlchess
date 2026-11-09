"""The HTTP boundary shares session authority without importing core routes."""

from fastapi.testclient import TestClient

from backend.app.infra.settings import Settings
from backend.app.learning.app import create_app as create_learning
from backend.app.main import create_app as create_core


def test_standalone_learning_reuses_core_session_and_revocation(tmp_path):
    origin = "http://testserver"
    settings = Settings(
        environment="test",
        public_origin=origin,
        database_url="sqlite+aiosqlite:///" + (tmp_path / "services.db").as_posix(),
        database_auto_create=True,
        learning_split=True,
    )
    with (
        TestClient(create_core(settings)) as core,
        TestClient(create_learning(settings)) as learning,
    ):
        assert core.get("/api/v1/learning/context").status_code == 404
        assert learning.get("/api/v1/me").status_code == 404
        assert learning.get("/health/ready").status_code == 200
        assert learning.get("/api/v1/learning/context").status_code == 401
        assert (
            core.post(
                "/api/v1/auth/guest", headers={"Origin": origin}, json={}
            ).status_code
            == 200
        )
        learning.cookies.update(core.cookies)
        assert learning.get("/api/v1/learning/context").json() == {
            "schema_version": 1,
            "learning_epoch": 0,
        }
        assert (
            learning.delete(
                "/api/v1/learning/data", headers={"Origin": origin}
            ).status_code
            == 403
        )
        assert (
            core.post(
                "/api/v1/logout",
                headers={
                    "Origin": origin,
                    "X-CSRF-Token": core.cookies["mlchess_csrf"],
                },
            ).status_code
            == 204
        )
        assert learning.get("/api/v1/learning/context").status_code == 401
