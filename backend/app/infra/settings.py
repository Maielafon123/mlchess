"""Fail-closed environment settings; no secrets are needed by the A-004 scaffold."""

from __future__ import annotations

from ipaddress import ip_address
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def canonical_origin(value: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or "*" in parsed.netloc
    ):
        raise ValueError("An explicit HTTP(S) origin is required")
    if (
        parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise ValueError(
            "Origins cannot include credentials, paths, queries or fragments"
        )
    if any(char.isspace() for char in value) or "\\" in value:
        raise ValueError("Invalid origin characters")
    host = parsed.hostname.lower()
    if ":" in host:
        host = "[" + host + "]"
    port = parsed.port
    if port is not None and not 1 <= port <= 65535:
        raise ValueError("Invalid port")
    default_port = 443 if parsed.scheme == "https" else 80
    return f"{parsed.scheme}://{host}" + (
        f":{port}" if port is not None and port != default_port else ""
    )


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MLCHESS_",
        env_file=None,
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
    )
    environment: Literal["development", "test", "staging", "production"] = "development"
    public_origin: str = "http://127.0.0.1:8000"
    dev_auth_enabled: bool = False
    session_ttl_seconds: int = Field(default=3600, ge=60, le=86400)
    readiness_timeout_ms: int = Field(default=500, ge=10, le=5000)
    database_url: str | None = Field(default=None, repr=False)
    database_auto_create: bool = False
    invitation_secret: str | None = Field(
        default=None, pattern=r"^[A-Za-z0-9_-]{43,128}$", repr=False
    )
    google_client_id: str = Field(default="", max_length=255)
    google_client_secret: SecretStr = Field(default=SecretStr(""), repr=False)
    trust_loopback_gateway: bool = False
    learning_split: bool = False
    redis_url: str | None = Field(default=None, repr=False)
    coach_openai_model: str = Field(default="", pattern=r"^[A-Za-z0-9_.-]{0,60}$")
    coach_openai_api_key: SecretStr = Field(default=SecretStr(""), repr=False)

    @field_validator("public_origin")
    @classmethod
    def normalize_origin(cls, value: str) -> str:
        return canonical_origin(value)

    @model_validator(mode="after")
    def production_guards(self):
        if self.redis_url and not self.redis_url.startswith(("redis://", "rediss://")):
            raise ValueError("Redis requires an explicit redis:// or rediss:// URL")
        google_secret = self.google_client_secret.get_secret_value()
        if bool(self.google_client_id) != bool(google_secret):
            raise ValueError("Set both Google OAuth credentials or neither")
        if self.google_client_id:
            if (
                not self.google_client_id.endswith(".apps.googleusercontent.com")
                or any(char.isspace() for char in self.google_client_id + google_secret)
                or len(google_secret) > 255
            ):
                raise ValueError("Invalid Google OAuth client configuration")
            origin = urlsplit(self.public_origin)
            host = origin.hostname
            try:
                numeric_host = ip_address(host)
            except ValueError:
                numeric_host = None
            loopback = host == "localhost" or (
                numeric_host and numeric_host.is_loopback
            )
            if self.environment in {"staging", "production"} and (
                numeric_host or loopback or "." not in host
            ):
                raise ValueError(
                    "Google OAuth on staging/production requires a DNS name"
                )
            if origin.scheme != "https" and not loopback:
                raise ValueError("Google OAuth requires HTTPS except on localhost")
            if self.database_url is None and self.environment != "test":
                raise ValueError("Google OAuth requires durable persistence")
        if self.database_url is not None and not self.database_url.startswith(
            ("postgresql+asyncpg://", "sqlite+aiosqlite://")
        ):
            raise ValueError("Unsupported asynchronous database driver")
        if self.environment in {"staging", "production"}:
            if self.database_auto_create:
                raise ValueError("Deploy schema changes using Alembic")
            if self.database_url and not self.database_url.startswith(
                "postgresql+asyncpg://"
            ):
                raise ValueError("Deployed persistence requires PostgreSQL")
            if not self.public_origin.startswith("https://"):
                raise ValueError("Staging/production requires HTTPS")
            if self.dev_auth_enabled:
                raise ValueError(
                    "Development authentication is forbidden outside development/test"
                )
        return self
