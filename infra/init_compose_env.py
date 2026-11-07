"""Create private local Compose settings without printing secrets or overwriting."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import secrets
from urllib.parse import urlsplit


def create(path: Path, origin: str) -> None:
    parsed = urlsplit(origin)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"localhost", "127.0.0.1"}
        or parsed.username
        or parsed.password
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Private development origin must be HTTP localhost/127.0.0.1")
    port = parsed.port or 80
    if not 1024 <= port <= 65535:
        raise ValueError("Use an unprivileged port between 1024 and 65535")
    content = (
        f"MLCHESS_PUBLIC_ORIGIN=http://{parsed.hostname}:{port}\n"
        f"MLCHESS_HTTP_PORT={port}\n"
        f"POSTGRES_PASSWORD={secrets.token_urlsafe(32)}\n"
        f"REDIS_PASSWORD={secrets.token_urlsafe(32)}\n"
    )
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
        stream.write(content)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(".env.dev.local"))
    parser.add_argument("--origin", default="http://localhost:8080")
    args = parser.parse_args()
    try:
        create(args.output, args.origin)
    except (OSError, ValueError):
        parser.exit(
            1, "Settings not created: check path, existing file and loopback origin.\n"
        )
    print("Private Compose settings created; values are not logged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
