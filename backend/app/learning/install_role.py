"""Provision only the application-owned learning PostgreSQL role after migration."""

import asyncio
import os
import re

from sqlalchemy import text

from backend.app.infra.db import create_engine

ROLE = "mlchess_learning"
CATALOG = ("lessons", "puzzles")
PROGRESS = (
    "learning_profiles",
    "learning_receipts",
    "lesson_progress",
    "progress_events",
    "puzzle_attempts",
    "puzzle_states",
    "student_skills",
)


async def provision(database_url: str, password: str) -> None:
    if not database_url.startswith("postgresql+asyncpg://"):
        raise ValueError("Learning roles require PostgreSQL")
    if not re.fullmatch(r"[A-Za-z0-9_-]{43,128}", password):
        raise ValueError("Use a unique URL-safe random learning password")
    engine = create_engine(database_url)
    try:
        async with engine.begin() as connection:
            # Protect provisioning from another migration job on the same cluster.
            await connection.execute(
                text("SELECT pg_advisory_xact_lock(75012026110916)")
            )
            existing = (
                await connection.execute(
                    text(
                        "SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls "
                        "FROM pg_catalog.pg_roles WHERE rolname = :role"
                    ),
                    {"role": ROLE},
                )
            ).one_or_none()
            if existing and any(existing):
                raise RuntimeError("Existing learning role has elevated privileges")
            quoted = await connection.scalar(
                text("SELECT pg_catalog.quote_literal(:secret)"), {"secret": password}
            )
            verb = "ALTER" if existing else "CREATE"
            await connection.exec_driver_sql(
                f"{verb} ROLE {ROLE} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
                f"NOINHERIT NOREPLICATION NOBYPASSRLS CONNECTION LIMIT 8 PASSWORD {quoted}"
            )
            await connection.exec_driver_sql(f"GRANT USAGE ON SCHEMA public TO {ROLE}")
            await connection.exec_driver_sql(
                f"REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {ROLE}"
            )
            await connection.exec_driver_sql(
                f"GRANT SELECT ON {', '.join('public.' + table for table in CATALOG)} TO {ROLE}"
            )
            await connection.exec_driver_sql(
                f"GRANT SELECT, INSERT, UPDATE, DELETE ON "
                f"{', '.join('public.' + table for table in PROGRESS)} TO {ROLE}"
            )
            await connection.exec_driver_sql(
                f"GRANT EXECUTE ON FUNCTION public.mlchess_learning_session(text) TO {ROLE}"
            )
    finally:
        await engine.dispose()


def main():
    try:
        asyncio.run(
            provision(
                os.environ["MLCHESS_DATABASE_URL"],
                os.environ["MLCHESS_LEARNING_PASSWORD"],
            )
        )
    except Exception:
        raise SystemExit(
            "Learning database permissions could not be installed"
        ) from None
    print("Learning database permissions installed")


if __name__ == "__main__":
    main()
