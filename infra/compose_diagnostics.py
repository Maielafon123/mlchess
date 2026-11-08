"""Print bounded application logs after redacting connection credentials."""

import argparse
import os
from pathlib import Path
import re
import subprocess


def redact(value: str, secrets: list[str]) -> str:
    for secret in sorted(set(secrets), key=len, reverse=True):
        if secret:
            value = value.replace(secret, "<redacted>")
    return re.sub(
        r"(postgresql(?:\+asyncpg)?://[^\s/:]+:)[^@\s]+@", r"\1<redacted>@", value
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--compose", action="append", required=True)
    args = parser.parse_args()
    secrets = []
    for line in args.env_file.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if separator and re.search("password|secret|token", key, re.I):
            secrets.append(value)
    secrets.extend(
        value
        for key, value in os.environ.items()
        if re.search("password|secret|token", key, re.I)
    )
    command = ["docker", "compose", "--env-file", str(args.env_file)]
    for compose in args.compose:
        command.extend(["-f", compose])
    result = subprocess.run(
        command
        + [
            "logs",
            "--no-color",
            "--tail",
            "65",
            "migrate",
            "postgres",
            "api",
            "worker",
            "web",
            "gateway",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=20,
    )
    print(redact(result.stdout + result.stderr, secrets))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
