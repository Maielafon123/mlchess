"""Test the browser boundary with real RSA signatures and a disposable store."""

from base64 import urlsafe_b64encode
from datetime import timedelta
from hashlib import sha256
import json
from urllib.parse import parse_qs, urlsplit

from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
import httpx
import jwt
import pytest

from backend.app.auth.cookies import HOST_SESSION, LEGACY_SESSION
from backend.app.auth.google import GoogleOIDC, JWKS, TOKEN
from backend.app.auth.service import now_utc
from backend.app.infra.security import SlidingWindowLimiter
from backend.app.infra.settings import Settings
from backend.app.main import create_app

ORIGIN = "https://chess.example.test"
CLIENT = "browser-fixture.apps.googleusercontent.com"
SECRET = "local-test-value"
START = "/api/v1/auth/oidc/start"
CALLBACK = "/api/v1/auth/oidc/callback"
FAILURE = "/play?auth=google-failed"
HEADERS = {"Origin": ORIGIN}


class SignedProvider:
    def __init__(self, key):
        self.key = key
        self.jwk = {
            **json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key())),
            "kid": "test-key",
            "alg": "RS256",
            "use": "sig",
        }
        self.authorization = None
        self.token_requests = 0
        self.claims = {}
        self.sign_with = key
        self.token_status = 200

    def __call__(self, request):
        if str(request.url) == JWKS:
            assert request.method == "GET"
            return httpx.Response(200, json={"keys": [self.jwk]})
        assert str(request.url) == TOKEN and request.method == "POST"
        self.token_requests += 1
        if self.token_status != 200:
            return httpx.Response(
                self.token_status, headers={"Location": "https://invalid.example.test/"}
            )
        data = parse_qs(request.content.decode("ascii"))
        assert data["code"] == ["exchange-once"]
        assert data["client_id"] == [CLIENT]
        assert data["client_secret"] == [SECRET]
        assert data["redirect_uri"] == [ORIGIN + CALLBACK]
        assert data["grant_type"] == ["authorization_code"]
        challenge = (
            urlsafe_b64encode(sha256(data["code_verifier"][0].encode("ascii")).digest())
            .rstrip(b"=")
            .decode("ascii")
        )
        assert challenge == self.authorization["code_challenge"][0]
        issued = int(now_utc().timestamp())
        claims = {
            "iss": "https://accounts.google.com",
            "sub": "128153333",
            "aud": CLIENT,
            "iat": issued,
            "exp": issued + 300,
            "nonce": self.authorization["nonce"][0],
            "name": " Alice\x00  Example ",
            "email": "never-store@example.test",
            **self.claims,
        }
        token = jwt.encode(
            claims, self.sign_with, algorithm="RS256", headers={"kid": "test-key"}
        )
        return httpx.Response(
            200, json={"id_token": token, "access_token": "never-store"}
        )


@pytest.fixture(scope="module")
def keys():
    return tuple(
        rsa.generate_private_key(public_exponent=65537, key_size=2048) for _ in range(2)
    )


@pytest.fixture
def oauth_settings(tmp_path):
    return Settings(
        environment="test",
        public_origin=ORIGIN,
        database_auto_create=True,
        database_url="sqlite+aiosqlite:///" + (tmp_path / "oidc.db").as_posix(),
        google_client_id=CLIENT,
        google_client_secret=SECRET,
    )


def configured(settings, provider):
    app = create_app(settings)
    app.state.google_oidc = GoogleOIDC(
        CLIENT, SECRET, ORIGIN + CALLBACK, transport=httpx.MockTransport(provider)
    )
    return app


def browser(app, **kwargs):
    return TestClient(app, base_url=ORIGIN, follow_redirects=False, **kwargs)


def guest(http):
    response = http.post("/api/v1/auth/guest", headers=HEADERS, json={})
    assert response.status_code == 200
    return response


def csrf(http):
    return {**HEADERS, "X-CSRF-Token": http.cookies["mlchess_csrf"]}


def start(http, provider):
    result = http.post(START, headers=csrf(http))
    assert result.status_code == 200, result.text
    authorization = urlsplit(result.json()["authorization_url"])
    assert authorization.netloc == "accounts.google.com"
    provider.authorization = parse_qs(authorization.query)
    assert provider.authorization["scope"] == ["openid profile"]
    assert provider.authorization["code_challenge_method"] == ["S256"]
    return provider.authorization["state"][0]


def finish(http, state, **params):
    return http.get(
        CALLBACK, params={"state": state, "code": "exchange-once", **params}
    )


def test_browser_binding_restart_replay_and_session_rotation(oauth_settings, keys):
    provider = SignedProvider(keys[0])
    with browser(configured(oauth_settings, provider)) as first:
        assert first.get("/api/v1/auth/providers").json() == {
            "schema_version": 1,
            "google": True,
        }
        assert first.post(START, headers=HEADERS).status_code == 401
        anon = guest(first).json()["id"]
        assert first.post(START, headers=HEADERS).status_code == 403
        assert (
            first.post(
                START, headers={**csrf(first), "Origin": "https://elsewhere.test"}
            ).status_code
            == 403
        )
        state = start(first, provider)
        saved = httpx.Cookies(first.cookies)
    # A new app instance consumes durable state; another browser cannot consume it.
    app = configured(oauth_settings, provider)
    with browser(app) as first, browser(app) as stranger:
        first.cookies.update(saved)
        guest(stranger)
        assert finish(stranger, state).headers["location"] == FAILURE
        assert finish(first, "x" * 43).headers["location"] == FAILURE
        assert provider.token_requests == 0
        success = finish(first, state, next="https://untrusted.test")
        assert success.status_code == 303 and success.headers["location"] == "/play"
        assert success.headers["referrer-policy"] == "no-referrer"
        assert first.cookies[HOST_SESSION] != saved[HOST_SESSION]
        assert first.cookies["mlchess_csrf"] != saved["mlchess_csrf"]
        account = first.get("/api/v1/me").json()
        assert account["kind"] == "account" and account["id"] != anon
        assert account["display_name"] == "Alice Example"
        assert set(account) == {
            "schema_version",
            "id",
            "kind",
            "display_name",
            "expires_at",
        }
        assert guest(first).json()["id"] == account["id"]
        assert finish(first, state).headers["location"] == FAILURE
        with browser(app, cookies=saved) as old:
            assert old.get("/api/v1/me").status_code == 401
        assert provider.token_requests == 1
        assert first.post("/api/v1/logout", headers=csrf(first)).status_code == 204
        assert first.get("/api/v1/me").status_code == 401
        guest(first)
        assert finish(first, start(first, provider)).headers["location"] == "/play"
        assert first.get("/api/v1/me").json()["id"] == account["id"]


@pytest.mark.parametrize(
    "invalid", ["signature", "issuer", "audience", "nonce", "expired", "redirect"]
)
def test_invalid_provider_result_consumes_state_without_signing_in(
    oauth_settings, keys, invalid
):
    provider = SignedProvider(keys[0])
    if invalid == "signature":
        provider.sign_with = keys[1]
    elif invalid == "redirect":
        provider.token_status = 302
    else:
        claims = {
            "issuer": {"iss": "https://evil.example.test"},
            "audience": {"aud": "wrong-client"},
            "nonce": {"nonce": "wrong-nonce"},
            "expired": {"exp": int(now_utc().timestamp()) - 300},
        }
        provider.claims = claims[invalid]
    with browser(configured(oauth_settings, provider)) as http:
        original = guest(http).json()["id"]
        state = start(http, provider)
        for _ in range(2):
            response = finish(http, state)
            assert (
                response.status_code == 303 and response.headers["location"] == FAILURE
            )
            assert response.headers.get_list("set-cookie") == []
            assert http.get("/api/v1/me").json()["id"] == original
        assert provider.token_requests == 1


def test_expiry_and_rate_limit(oauth_settings, keys, monkeypatch):
    provider = SignedProvider(keys[0])
    with browser(configured(oauth_settings, provider)) as http:
        guest(http)
        state = start(http, provider)
        then = now_utc() + timedelta(minutes=5, seconds=1)
        monkeypatch.setattr("backend.app.auth.oidc_attempts.now_utc", lambda: then)
        assert finish(http, state).headers["location"] == FAILURE
        assert provider.token_requests == 0
        for _ in range(5):
            start(http, provider)
        assert http.post(START, headers=csrf(http)).status_code == 429


def test_https_adopts_legacy_session_and_disabled_provider(oauth_settings):
    settings = oauth_settings.model_copy(update={"google_client_id": ""})
    app = create_app(settings)
    with browser(app) as first:
        initial = guest(first)
        cookie = next(
            item
            for item in initial.headers.get_list("set-cookie")
            if item.startswith(HOST_SESSION)
        )
        assert all(
            flag in cookie for flag in ("HttpOnly", "Path=/", "Secure", "SameSite=lax")
        )
        assert "Domain=" not in cookie
        token = first.cookies[HOST_SESSION]
        first.cookies.clear()
        first.cookies.set(LEGACY_SESSION, token, domain="chess.example.test")
        first.cookies.set(
            "mlchess_csrf", initial.cookies["mlchess_csrf"], domain="chess.example.test"
        )
        upgraded = guest(first)
        assert upgraded.json() == initial.json()
        assert upgraded.cookies[HOST_SESSION] == token
        assert LEGACY_SESSION not in first.cookies
        assert first.get("/api/v1/auth/providers").json()["google"] is False
        assert first.post(START, headers=csrf(first)).status_code == 404
        assert first.get(CALLBACK).status_code == 404


def test_trusted_loopback_gateway_keys_and_rejects_nonlocal_spoof(oauth_settings):
    settings = oauth_settings.model_copy(update={"trust_loopback_gateway": True})
    app = create_app(settings)
    app.state.guest_login_limiter = SlidingWindowLimiter(1, 60)
    with browser(app, client=("127.0.0.1", 4321)) as proxy:

        def guest_at(ip):
            proxy.cookies.clear()
            return proxy.post(
                "/api/v1/auth/guest",
                headers={**HEADERS, "X-MLChess-Client-IP": ip},
                json={},
            ).status_code

        assert guest_at("198.51.100.2") == 200
        assert guest_at("198.51.100.2") == 429
        assert guest_at("198.51.100.3") == 200
    with browser(app, client=("203.0.113.1", 4321)) as direct:
        assert guest(direct).status_code == 200
        direct.cookies.clear()
        assert (
            direct.post(
                "/api/v1/auth/guest",
                headers={**HEADERS, "X-MLChess-Client-IP": "192.0.2.5"},
                json={},
            ).status_code
            == 429
        )


def test_production_google_configuration_fails_closed_on_ip():
    with pytest.raises(ValueError, match="requires a DNS name"):
        Settings(
            environment="production",
            public_origin="https://192.0.2.1",
            google_client_id=CLIENT,
            google_client_secret=SECRET,
            database_url="postgresql+asyncpg://app:fixture@postgres/chess",
        )
