"""Verify deployed permissions without reading account or gameplay records."""

import asyncio

from sqlalchemy import text

from backend.app.infra.db import create_engine
from backend.app.infra.settings import Settings
from backend.app.learning.install_role import CATALOG, PROGRESS, ROLE


async def verify():
    engine = create_engine(Settings().database_url)
    try:
        async with engine.connect() as connection:

            async def table_privilege(table, privilege):
                return await connection.scalar(
                    text(
                        "SELECT has_table_privilege(current_user, :target, :permission)"
                    ),
                    {"target": "public." + table, "permission": privilege},
                )

            if await connection.scalar(text("SELECT current_user")) != ROLE:
                raise RuntimeError("Wrong learning role")
            for table in (
                "sessions",
                "users",
                "games",
                "game_states",
                "outbox_events",
                "oauth_attempts",
            ):
                if any(
                    [
                        await table_privilege(table, mode)
                        for mode in ("SELECT", "INSERT", "UPDATE", "DELETE")
                    ]
                ):
                    raise RuntimeError("Learning role has an unrelated table privilege")
            for table in CATALOG:
                if not await table_privilege(table, "SELECT") or await table_privilege(
                    table, "UPDATE"
                ):
                    raise RuntimeError("Incorrect learning catalog permissions")
            for table in PROGRESS:
                if not all(
                    [
                        await table_privilege(table, mode)
                        for mode in ("SELECT", "INSERT", "UPDATE", "DELETE")
                    ]
                ):
                    raise RuntimeError("Incorrect learning progress permissions")
            if not await connection.scalar(
                text(
                    "SELECT has_function_privilege(current_user, 'public.mlchess_learning_session(text)', 'EXECUTE')"
                )
            ):
                raise RuntimeError("Learning role cannot verify a session")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    try:
        asyncio.run(verify())
    except Exception:
        raise SystemExit("Learning database permission check failed") from None
    print("Learning role permissions verified")
