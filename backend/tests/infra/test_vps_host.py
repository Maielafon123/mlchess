"""Verify the chosen host overlay without inspecting protected host networking."""

import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize("domain", [False, True])
def test_rendered_vps_stack_has_no_bridges_nat_or_network_admin(tmp_path, domain):
    docker = shutil.which("docker")
    if not docker:
        pytest.skip("Docker Compose CLI is required (daemon is not needed)")
    env_file = tmp_path / "config.env"
    env_file.write_text("", encoding="utf-8")
    result = subprocess.run(
        [
            docker,
            "compose",
            "--env-file",
            str(env_file),
            "-f",
            "infra/compose.server.yml",
            "-f",
            "infra/compose.vps-host.yml",
            "config",
            "--format",
            "json",
        ],
        cwd=ROOT,
        env={
            **os.environ,
            "MLCHESS_IMAGE_TAG": "test",
            "MLCHESS_PUBLIC_ORIGIN": "https://chess.example.test"
            if domain
            else "https://203.0.113.10",
            "MLCHESS_SITE_ADDRESS": "chess.example.test" if domain else "203.0.113.10",
            "MLCHESS_BIND_ADDRESS": "203.0.113.10" if domain else "",
            "MLCHESS_INVITATION_SECRET": "x" * 43,
            "POSTGRES_PASSWORD": "disposable_config_only",
            "REDIS_PASSWORD": "disposable_config_only",
        },
        capture_output=True,
        text=True,
        timeout=20,
        check=True,
    )
    config = json.loads(result.stdout)
    assert not config.get("networks")
    services = config["services"]
    assert set(services) == {
        "api",
        "worker",
        "analysis-worker",
        "coach-worker",
        "clock-worker",
        "web",
        "gateway",
        "postgres",
        "redis",
        "migrate",
    }
    for service in services.values():
        assert service["network_mode"] == "host"
        assert not service.get("networks")
        assert not service.get("ports")
        assert not service.get("sysctls")
        assert not service.get("privileged")
        assert "NET_ADMIN" not in service.get("cap_add", [])
    assert services["gateway"]["cap_add"] == ["NET_BIND_SERVICE"]
    assert services["gateway"]["environment"]["MLCHESS_BIND_ADDRESS"] == "203.0.113.10"
    assert "ALL" in services["gateway"]["cap_drop"]
    tls_mounts = [
        mount for mount in services["gateway"]["volumes"] if mount["type"] == "volume"
    ]
    assert {mount["target"] for mount in tls_mounts} == {"/data", "/config"}
    assert all(mount["volume"]["nocopy"] for mount in tls_mounts)
    assert "listen_addresses=127.0.0.1" in services["postgres"]["command"]
    # Image entrypoint uses its standard Unix socket to create POSTGRES_DB.
    assert not any(
        "unix_socket_directories=" in item for item in services["postgres"]["command"]
    )
    assert "--bind 127.0.0.1" in " ".join(services["redis"]["command"])
    api_command = services["api"]["command"]
    assert api_command[api_command.index("--host") + 1] == "127.0.0.1"
    assert api_command[api_command.index("--port") + 1] == "58000"
    assert api_command[api_command.index("--ws") + 1] == "websockets"
    assert api_command[api_command.index("--ws-max-size") + 1] == "2048"
    assert api_command[api_command.index("--ws-max-queue") + 1] == "4"
    assert api_command[api_command.index("--ws-per-message-deflate") + 1] == "false"
    for name in (
        "api",
        "worker",
        "analysis-worker",
        "coach-worker",
        "clock-worker",
        "migrate",
    ):
        assert (
            "@127.0.0.1:55432/" in services[name]["environment"]["MLCHESS_DATABASE_URL"]
        )
        assert services[name]["environment"]["MLCHESS_DEV_AUTH_ENABLED"] == "false"
