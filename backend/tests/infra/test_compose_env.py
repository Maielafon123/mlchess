import os
import re

import pytest

from infra.init_compose_env import create


def test_private_secrets_are_unique_and_existing_file_is_not_overwritten(tmp_path):
    path = tmp_path / ".env.dev.local"
    create(path, "http://localhost:8080")
    original = path.read_text()
    values = dict(line.split("=", 1) for line in original.splitlines())
    assert values["MLCHESS_HTTP_PORT"] == "8080"
    assert re.fullmatch(r"[A-Za-z0-9_-]{43}", values["POSTGRES_PASSWORD"])
    assert values["POSTGRES_PASSWORD"] != values["REDIS_PASSWORD"]
    assert re.fullmatch(r"[A-Za-z0-9_-]{43}", values["MLCHESS_INVITATION_SECRET"])
    if os.name != "nt":
        assert path.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        create(path, "http://localhost:8081")
    assert path.read_text() == original


@pytest.mark.parametrize(
    "origin",
    [
        "http://0.0.0.0:8080",
        "http://example.org:8080",
        "https://localhost:8080",
        "http://user:secret@localhost:8080",
        "http://localhost:8080/api",
        "http://localhost:8080/?x=1",
        "http://localhost:80",
        "http://localhost:99999",
    ],
)
def test_private_stack_rejects_public_or_malformed_origins(tmp_path, origin):
    path = tmp_path / ".env.dev.local"
    with pytest.raises(ValueError):
        create(path, origin)
    assert not path.exists()


def test_server_settings_use_public_ip_https_and_never_development_auth(tmp_path):
    path = tmp_path / ".env.server.local"
    create(path, "https://1.1.1.1", server=True)
    values = dict(line.split("=", 1) for line in path.read_text().splitlines())
    assert values["MLCHESS_PUBLIC_ORIGIN"] == "https://1.1.1.1"
    assert values["MLCHESS_SITE_ADDRESS"] == "1.1.1.1"
    assert "MLCHESS_HTTP_PORT" not in values


@pytest.mark.parametrize(
    "origin",
    [
        "http://1.1.1.1",
        "https://127.0.0.1",
        "https://10.0.0.1",
        "https://1.1.1.1:8443",
        "https://example.test",
    ],
)
def test_server_settings_reject_private_ips_and_nonstandard_https(tmp_path, origin):
    path = tmp_path / ".env.server.local"
    with pytest.raises(ValueError):
        create(path, origin, server=True)
    assert not path.exists()
