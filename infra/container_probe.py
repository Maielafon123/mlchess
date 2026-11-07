"""Small container probes. Never print connection URLs or credentials."""

from __future__ import annotations

import asyncio
import os
import sys
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from sqlalchemy import text
from backend.app.infra.db import create_engine


async def database() -> None:
    engine = create_engine(os.environ["MLCHESS_DATABASE_URL"])
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT id FROM worker_jobs LIMIT 1"))
    finally:
        await engine.dispose()


def main() -> int:
    try:
        if sys.argv[1:] == ["worker"]:
            asyncio.run(database())
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
