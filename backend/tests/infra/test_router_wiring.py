from backend.app.main import create_app
from backend.app.infra.settings import Settings


def test_composed_api_exposes_session_routes():
    app = create_app(Settings(environment="test", public_origin="http://testserver"))
    assert app.state.auth_service is not None
    assert app.openapi()["paths"].keys() >= {
        "/api/v1/me",
        "/api/v1/logout",
        "/api/v1/auth/dev-login",
    }
