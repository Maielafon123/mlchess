"""Share cookie selection between HTTP and WebSocket authentication."""

from starlette.requests import HTTPConnection
from starlette.responses import Response

LEGACY_SESSION = "mlchess_session"
HOST_SESSION = "__Host-mlchess_session"
CSRF_COOKIE = "mlchess_csrf"


def secure_session(connection: HTTPConnection) -> bool:
    return connection.app.state.settings.public_origin.startswith("https://")


def session_token(connection: HTTPConnection) -> str | None:
    cookies = connection.cookies
    if secure_session(connection) and HOST_SESSION in cookies:
        return cookies[HOST_SESSION]
    return cookies.get(LEGACY_SESSION)


def write_session(
    response: Response,
    connection: HTTPConnection,
    token: str,
    csrf: str,
    max_age: int,
) -> None:
    secure = secure_session(connection)
    common = {"secure": secure, "samesite": "lax", "path": "/", "max_age": max_age}
    response.set_cookie(
        HOST_SESSION if secure else LEGACY_SESSION, token, httponly=True, **common
    )
    response.set_cookie(CSRF_COOKIE, csrf, **common)
    if secure and LEGACY_SESSION in connection.cookies:
        response.delete_cookie(LEGACY_SESSION, secure=True, httponly=True, path="/")


def clear_session(response: Response, connection: HTTPConnection) -> None:
    secure = secure_session(connection)
    response.delete_cookie(LEGACY_SESSION, path="/", secure=secure, httponly=True)
    response.delete_cookie(CSRF_COOKIE, path="/", secure=secure)
    if secure:
        response.delete_cookie(HOST_SESSION, path="/", secure=True, httponly=True)
