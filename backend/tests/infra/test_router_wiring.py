from backend.app.main import create_app
from backend.app.infra.settings import Settings


def test_b_owned_router_boundaries_are_composed_without_routes():
    app = create_app(Settings(environment="test", public_origin="http://testserver"))
    assert app.state.auth_service is not None
    assert {route.path for route in app.routes} >= {
        "/api/v1/me",
        "/api/v1/logout",
        "/api/v1/auth/dev-login",
    }
