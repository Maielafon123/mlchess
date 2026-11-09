"""Google code exchange and bounded verification of Google-signed ID tokens."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import hmac
import json
import re
from time import monotonic
from unicodedata import category
from urllib.parse import urlencode

import httpx
import jwt

AUTHORIZE = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN = "https://oauth2.googleapis.com/token"
JWKS = "https://www.googleapis.com/oauth2/v3/certs"
ISSUERS = ("https://accounts.google.com", "accounts.google.com")


class GoogleLoginFailed(Exception):
    """Provider refusal, unavailability or invalid identity."""


@dataclass(frozen=True)
class GoogleIdentity:
    subject: str
    name: str


class GoogleOIDC:
    def __init__(
        self,
        client_id: str,
        secret: str,
        redirect_uri: str,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.client_id = client_id
        self._secret = secret
        self.redirect_uri = redirect_uri
        self._transport = transport
        self._keys: dict[str, jwt.PyJWK] = {}
        self._expiry = 0.0
        self._refresh_allowed = 0.0
        self._lock = asyncio.Lock()

    def authorization_url(self, state: str, nonce: str, challenge: str) -> str:
        return (
            AUTHORIZE
            + "?"
            + urlencode(
                {
                    "client_id": self.client_id,
                    "redirect_uri": self.redirect_uri,
                    "response_type": "code",
                    "scope": "openid profile",
                    "state": state,
                    "nonce": nonce,
                    "code_challenge": challenge,
                    "code_challenge_method": "S256",
                }
            )
        )

    @staticmethod
    async def _json(client, method, url, *, limit, **kwargs):
        async with client.stream(method, url, **kwargs) as response:
            if (
                response.status_code != 200
                or response.headers.get("Content-Encoding", "identity").lower()
                != "identity"
            ):
                raise GoogleLoginFailed
            data = bytearray()
            async for chunk in response.aiter_bytes(chunk_size=4096):
                data.extend(chunk)
                if len(data) > limit:
                    raise GoogleLoginFailed
            payload = json.loads(data)
            if not isinstance(payload, dict):
                raise GoogleLoginFailed
            return payload, response.headers

    async def _key(self, client, kid: str) -> jwt.PyJWK:
        async with self._lock:
            now = monotonic()
            if now < self._expiry and kid in self._keys:
                return self._keys[kid]
            if now < self._refresh_allowed:
                raise GoogleLoginFailed
            self._refresh_allowed = now + 5
            payload, headers = await self._json(client, "GET", JWKS, limit=65536)
            keys = payload.get("keys")
            if not isinstance(keys, list) or not 1 <= len(keys) <= 16:
                raise GoogleLoginFailed
            valid = {}
            for candidate in keys:
                if (
                    isinstance(candidate, dict)
                    and candidate.get("kty") == "RSA"
                    and candidate.get("use", "sig") == "sig"
                    and candidate.get("alg", "RS256") == "RS256"
                    and "d" not in candidate
                    and isinstance(candidate.get("kid"), str)
                    and re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", candidate["kid"])
                ):
                    key_id = candidate["kid"]
                    if key_id in valid:
                        raise GoogleLoginFailed
                    valid[key_id] = jwt.PyJWK.from_dict(candidate, algorithm="RS256")
            control = headers.get("Cache-Control", "").lower()
            age = re.search(r"(?:^|,)\s*max-age=(\d{1,8})(?:\s*,|$)", control)
            ttl = min(int(age[1]), 900) if age else 300
            if "no-store" in control or "no-cache" in control:
                ttl = 0
            self._keys, self._expiry = valid, monotonic() + ttl
            if kid not in valid:
                raise GoogleLoginFailed
            return valid[kid]

    async def identity(self, code: str, verifier: str, nonce: str) -> GoogleIdentity:
        try:
            async with (
                asyncio.timeout(7),
                httpx.AsyncClient(
                    timeout=4,
                    follow_redirects=False,
                    trust_env=False,
                    transport=self._transport,
                    headers={
                        "Accept": "application/json",
                        "Accept-Encoding": "identity",
                    },
                ) as client,
            ):
                payload, _headers = await self._json(
                    client,
                    "POST",
                    TOKEN,
                    limit=32768,
                    data={
                        "grant_type": "authorization_code",
                        "code": code,
                        "redirect_uri": self.redirect_uri,
                        "client_id": self.client_id,
                        "client_secret": self._secret,
                        "code_verifier": verifier,
                    },
                )
                token = payload.get("id_token")
                if not isinstance(token, str) or not 1 <= len(token) <= 8192:
                    raise GoogleLoginFailed
                header = jwt.get_unverified_header(token)
                kid = header.get("kid")
                if (
                    header.get("alg") != "RS256"
                    or not isinstance(kid, str)
                    or not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", kid)
                    or any(field in header for field in ("jku", "x5u", "jwk", "crit"))
                ):
                    raise GoogleLoginFailed
                key = await self._key(client, kid)
                claims = jwt.decode(
                    token,
                    key,
                    algorithms=["RS256"],
                    issuer=ISSUERS,
                    audience=self.client_id,
                    leeway=20,
                    options={
                        "require": ["iss", "aud", "exp", "iat", "sub", "nonce"],
                        "strict_aud": True,
                        "enforce_minimum_key_length": True,
                    },
                )
        except (
            TimeoutError,
            httpx.HTTPError,
            jwt.PyJWTError,
            ValueError,
            TypeError,
            RecursionError,
        ):
            raise GoogleLoginFailed from None
        actual_nonce, subject = claims["nonce"], claims["sub"]
        if (
            not isinstance(actual_nonce, str)
            or not actual_nonce.isascii()
            or not hmac.compare_digest(actual_nonce, nonce)
            or not isinstance(subject, str)
            or not re.fullmatch(r"[A-Za-z0-9_-]{1,248}", subject)
            or claims.get("azp", self.client_id) != self.client_id
        ):
            raise GoogleLoginFailed
        name = claims.get("name")
        if isinstance(name, str):
            name = "".join(c for c in name if not category(c).startswith("C"))
            name = " ".join(name.split())[:80]
        return GoogleIdentity(
            "google:" + subject, name if isinstance(name, str) and name else "Игрок"
        )
