"""Independent outbox dispatcher; Redis latency never holds a game row lock."""

import argparse
import asyncio
import json

from sqlalchemy import func, select, text

from backend.app.infra.db import create_engine, session_factory
from backend.app.infra.models import OutboxEvent
from backend.app.infra.outbox import OutboxDispatcher
from backend.app.infra.settings import Settings
from backend.app.realtime.broker import RedisPublisher, STREAM, redis_client


async def pending(factory):
    async with factory() as session:
        return await session.scalar(
            select(func.count())
            .select_from(OutboxEvent)
            .where(OutboxEvent.published_at.is_(None))
        )


async def run(settings, check):
    if not settings.database_url or not settings.database_url.startswith(
        "postgresql+asyncpg://mlchess_relay:"
    ):
        raise ValueError("The relay requires its restricted database role")
    if not settings.redis_url:
        raise ValueError("The relay requires a Redis URL")
    engine = create_engine(
        settings.database_url, pool_size=2, max_overflow=0, pool_timeout=2
    )
    factory = session_factory(engine)
    try:
        async with engine.connect() as connection:
            correct = await connection.scalar(
                text(
                    "SELECT current_user = 'mlchess_relay' "
                    "AND NOT has_table_privilege(current_user, 'public.games', 'SELECT') "
                    "AND NOT has_table_privilege(current_user, 'public.sessions', 'SELECT') "
                    "AND NOT has_column_privilege(current_user, 'public.outbox_events', 'payload', 'SELECT') "
                    "AND has_column_privilege(current_user, 'public.outbox_events', 'published_at', 'UPDATE')"
                )
            )
            if not correct:
                raise RuntimeError("Invalid outbox relay permissions")
        if check == "pending":
            count = await pending(factory)
            if not count:
                raise RuntimeError("Expected committed unpublished events")
            print(json.dumps({"status": "pending_events_preserved", "events": count}))
            return
        async with redis_client(settings.redis_url) as client:
            if check == "drained":
                async with asyncio.timeout(20):
                    while await pending(factory):
                        await asyncio.sleep(0.25)
                records = await client.xrevrange(STREAM, count=16)
                if not records or any(
                    not set(fields) <= {"event_id", "event_type", "game_id"}
                    for _, fields in records
                ):
                    raise RuntimeError("Missing or unexpected broker records")
                async with factory() as session:
                    recent = await session.scalars(
                        select(OutboxEvent.id)
                        .where(OutboxEvent.published_at.is_not(None))
                        .order_by(OutboxEvent.published_at.desc(), OutboxEvent.id)
                        .limit(5)
                    )
                    if {str(item) for item in recent} - {
                        fields["event_id"] for _, fields in records
                    }:
                        raise RuntimeError(
                            "Acknowledged SQL events are absent from Redis"
                        )
                print(
                    json.dumps(
                        {
                            "status": "outbox_recovered",
                            "recent_transport_entries": len(records),
                        }
                    )
                )
                return
            dispatcher = OutboxDispatcher(factory, RedisPublisher(client))
            unavailable = False
            while True:
                try:
                    async with asyncio.timeout(4):
                        count = await dispatcher.dispatch_batch(limit=16)
                except Exception:
                    if not unavailable:
                        print(json.dumps({"event": "outbox.unavailable"}), flush=True)
                    unavailable = True
                    await asyncio.sleep(1)
                    continue
                if dispatcher.transport_failed and not unavailable:
                    print(json.dumps({"event": "outbox.unavailable"}), flush=True)
                elif unavailable and not dispatcher.transport_failed:
                    print(json.dumps({"event": "outbox.available"}), flush=True)
                unavailable = dispatcher.transport_failed
                if not count:
                    await asyncio.sleep(0.5)
    finally:
        await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", choices=("pending", "drained"))
    args = parser.parse_args()
    try:
        asyncio.run(run(Settings(), args.check))
    except Exception:
        raise SystemExit("Outbox relay check or startup failed") from None


if __name__ == "__main__":
    main()
