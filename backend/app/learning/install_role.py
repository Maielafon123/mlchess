"""Provision application-owned PostgreSQL roles after migration."""

import asyncio
import os
import re

from sqlalchemy import text

from backend.app.infra.db import create_engine

ROLE = "mlchess_learning"
RELAY_ROLE = "mlchess_relay"
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


async def provision(database_url: str, password: str, *, role: str = ROLE) -> None:
    if not database_url.startswith("postgresql+asyncpg://"):
        raise ValueError("Service roles require PostgreSQL")
    if role not in {ROLE, RELAY_ROLE} or not re.fullmatch(
        r"[A-Za-z0-9_-]{43,128}", password
    ):
        raise ValueError("Use an application role and a unique URL-safe password")
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
                    {"role": role},
                )
            ).one_or_none()
            if existing and any(existing):
                raise RuntimeError("Existing application role has elevated privileges")
            quoted = await connection.scalar(
                text("SELECT pg_catalog.quote_literal(CAST(:secret AS text))"),
                {"secret": password},
            )
            verb = "ALTER" if existing else "CREATE"
            await connection.exec_driver_sql(
                f"{verb} ROLE {role} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
                f"NOINHERIT NOREPLICATION NOBYPASSRLS CONNECTION LIMIT 8 PASSWORD {quoted}"
            )
            await connection.exec_driver_sql(f"GRANT USAGE ON SCHEMA public TO {role}")
            await connection.exec_driver_sql(
                f"REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {role}"
            )
            if role == RELAY_ROLE:
                await connection.exec_driver_sql(
                    f"GRANT SELECT (id, event_type, aggregate_type, aggregate_id, attempts, created_at, published_at), "
                    f"UPDATE (attempts, published_at) ON public.outbox_events TO {role}"
                )
                return
            await connection.exec_driver_sql(
                f"GRANT SELECT ON {', '.join('public.' + table for table in CATALOG)} TO {ROLE}"
            )
            await connection.exec_driver_sql(
                f"GRANT SELECT, INSERT, UPDATE, DELETE ON "
                f"{', '.join('public.' + table for table in PROGRESS)} TO {ROLE}"
            )
            # Logical restore may omit ACLs; keep the definer function private
            # when recreating service roles as part of recovery.
            await connection.exec_driver_sql(
                "REVOKE ALL ON FUNCTION public.mlchess_learning_session(text) FROM PUBLIC"
            )
            await connection.exec_driver_sql(
                f"GRANT EXECUTE ON FUNCTION public.mlchess_learning_session(text) TO {ROLE}"
            )
    finally:
        await engine.dispose()


async def provision_services():
    url = os.environ["MLCHESS_DATABASE_URL"]
    await provision(url, os.environ["MLCHESS_LEARNING_PASSWORD"])
    if password := os.environ.get("MLCHESS_RELAY_PASSWORD"):
        await provision(url, password, role=RELAY_ROLE)


def main():
    try:
        asyncio.run(provision_services())
    except Exception:
        raise SystemExit(
            "Application database permissions could not be installed"
        ) from None
    print("Application database permissions installed")


if __name__ == "__main__":
    main()
