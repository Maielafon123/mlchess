"""Redis wake notifications. Every client-visible frame still comes from SQL."""

import asyncio
from contextlib import asynccontextmanager, suppress
import re
from uuid import UUID

from redis.asyncio import Redis
from redis.asyncio.retry import Retry
from redis.backoff import NoBackoff
from redis.exceptions import RedisError

STREAM = "mlchess:outbox:wake:v1"
MAX_ENTRIES = 2048


def redis_client(url):
    return Redis.from_url(
        url,
        decode_responses=True,
        socket_connect_timeout=0.5,
        socket_timeout=2,
        retry=Retry(NoBackoff(), 0),
        max_connections=2,
        health_check_interval=10,
    )


class RedisPublisher:
    def __init__(self, client):
        self.client = client

    async def publish(self, *, event_id, event_type, aggregate_type, aggregate_id):
        fields = {"event_id": str(event_id)}
        if re.fullmatch(r"[a-z][a-z0-9_.-]{0,63}", event_type):
            fields["event_type"] = event_type
        if aggregate_type == "game":
            fields["game_id"] = str(aggregate_id)
        # Do not copy event payloads, analysis, moves, actor ids or session data.
        await self.client.xadd(STREAM, fields, maxlen=MAX_ENTRIES, approximate=False)


class GameWakeups:
    """A bounded set of wake signals, allocated only after socket admission."""

    def __init__(self):
        self.listeners: dict[UUID, set[asyncio.Event]] = {}

    def register(self, game_id):
        signal = asyncio.Event()
        self.listeners.setdefault(game_id, set()).add(signal)
        return signal

    def remove(self, game_id, signal):
        listeners = self.listeners[game_id]
        listeners.remove(signal)
        if not listeners:
            del self.listeners[game_id]

    def publish(self, game_id):
        for signal in self.listeners.get(game_id, ()):
            signal.set()


async def consume(client, wakeups):
    cursor = "0-0"
    while True:
        try:
            results = await client.xread({STREAM: cursor}, count=128, block=1000)
        except (RedisError, OSError, TimeoutError):
            # On reconnect, re-reading recent hints is safe. SQL is authoritative.
            cursor = "0-0"
            await asyncio.sleep(1)
            continue
        for _stream, rows in results:
            for cursor, fields in rows:
                game = fields.get("game_id")
                if game:
                    with suppress(ValueError):
                        wakeups.publish(UUID(game))


def broker_runtime(url):
    @asynccontextmanager
    async def runtime(app):
        if not url:
            yield
            return
        async with redis_client(url) as client:
            app.state.wakeups = GameWakeups()
            task = asyncio.create_task(consume(client, app.state.wakeups))
            try:
                yield
            finally:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
                app.state.wakeups = None

    return runtime
