"""Small container probes. Never print connection URLs or credentials."""

from __future__ import annotations

import asyncio
import os
import sys
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


async def database(kind: str = "worker") -> None:
    # A health subprocess shares the worker's CPU quota. Avoid importing the ORM
    # and application graph on every probe, especially on a 0.4 CPU VPS worker.
    import asyncpg

    url = os.environ["MLCHESS_DATABASE_URL"]
    if not url.startswith("postgresql+asyncpg://"):
        raise ValueError("Worker probe requires PostgreSQL")
    connection = await asyncpg.connect(
        url.replace("postgresql+asyncpg://", "postgresql://", 1),
        timeout=2,
        command_timeout=2,
    )
    try:
        query = {
            "worker": "SELECT id FROM worker_jobs LIMIT 1",
            "clock": "SELECT clock_deadline_at FROM games LIMIT 1",
        }[kind]
        await connection.fetchval(query)
    finally:
        await connection.close(timeout=1)


def main() -> int:
    try:
        if sys.argv[1:] == ["worker"]:
            asyncio.run(database())
        elif sys.argv[1:] == ["clock"]:
            asyncio.run(database("clock"))
        else:
            origin = os.environ["MLCHESS_PUBLIC_ORIGIN"]
            request = Request(
                "http://127.0.0.1:8000/health/ready",
                headers={"Host": urlsplit(origin).netloc},
            )
            with urlopen(request, timeout=3) as response:
                if response.status != 200:
                    return 1
        return 0
    except Exception:
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
