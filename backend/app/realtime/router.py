"""Bounded read-only WebSockets with mandatory Origin/session/participant checks."""

import asyncio
from contextlib import asynccontextmanager, suppress
import json
import time
from uuid import UUID, uuid4

from anyio import CancelScope
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ConfigDict, model_validator

from backend.app.auth.cookies import session_token
from backend.app.infra.problems import PublicProblem
from backend.app.infra.settings import canonical_origin
from backend.app.infra.http import default_request_logger
from backend.app.infra.generated.contracts import GameSubscribeV1


class Subscribe(GameSubscribeV1):
    model_config = ConfigDict(extra="forbid", strict=True)

    @model_validator(mode="before")
    @classmethod
    def strict_integer(cls, data):
        if not isinstance(data, dict) or type(data.get("after_seq")) is not int:
            raise ValueError("Integer cursor required")
        return data


@asynccontextmanager
async def bounded_sql():
    # Finish releasing SQLAlchemy connections before an outer ASGI cancel scope
    # interrupts the socket. The read retains its own hard timeout.
    with CancelScope(shield=True):
        async with asyncio.timeout(5):
            yield


def unique_fields(pairs):
    result = {}
    for name, value in pairs:
        if name in result:
            raise ValueError("Duplicate subscription field")
        result[name] = value
    return result


class Connections:
    """Event-loop-local admission; increment/decrement never yields."""

    def __init__(self, *, total=32, per_actor=4):
        self.limit, self.per_actor, self.actors = total, per_actor, {}

    def acquire(self, actor):
        if (
            sum(self.actors.values()) >= self.limit
            or self.actors.get(actor, 0) >= self.per_actor
        ):
            return False
        self.actors[actor] = self.actors.get(actor, 0) + 1
        return True

    def release(self, actor):
        count = self.actors.get(actor, 0)
        if count <= 1:
            self.actors.pop(actor, None)
        else:
            self.actors[actor] = count - 1


def origin_allowed(socket):
    origins, hosts = socket.headers.getlist("origin"), socket.headers.getlist("host")
    expected = socket.app.state.settings.public_origin
    try:
        return (
            len(origins) == len(hosts) == 1
            and not origins[0].endswith("/")
            and canonical_origin(origins[0]) == expected
            and canonical_origin(expected.split("://", 1)[0] + "://" + hosts[0])
            == expected
            and not socket.scope.get("query_string")
        )
    except ValueError:
        return False


def create_router():
    router = APIRouter()

    @router.websocket("/ws/v1/games/{game_id}")
    async def stream(socket: WebSocket, game_id: UUID):
        request_id, started, recorded = str(uuid4()), time.monotonic(), False

        def record_close(code):
            nonlocal recorded
            if recorded:
                return
            recorded = True
            socket.app.state.metrics.increment("websocket_closed_total", code=str(code))
            default_request_logger().info(
                "WebSocket closed",
                extra={
                    "event": "websocket.closed",
                    "request_id": request_id,
                    "method": "WS",
                    "status": code,
                    "duration_ms": int((time.monotonic() - started) * 1000),
                },
            )

        async def close(code):
            record_close(code)
            await socket.close(code=code)

        if not origin_allowed(socket):
            await close(1008)
            return
        token = session_token(socket)
        auth = socket.app.state.auth_service
        try:
            async with bounded_sql():
                record = await auth.authenticate(token)
        except Exception:
            await close(1011)
            return
        if record is None:
            await close(4401)
            return
        service = socket.app.state.event_stream
        if service is None:
            await close(1011)
            return
        # Check ACL before accepting, without allocating a cursor or holding a TX.
        try:
            async with bounded_sql():
                await service.read(game_id, record.user.id, 0, bootstrap=True)
        except PublicProblem:
            await close(4403)
            return
        except Exception:
            await close(1011)
            return
        connections = socket.app.state.ws_connections
        if not connections.acquire(record.user.id):
            await close(1013)
            return
        receiver = None
        wakeups = socket.app.state.wakeups
        wake = None
        try:
            await socket.accept()
            try:
                async with asyncio.timeout(5):
                    message = await socket.receive()
            except TimeoutError:
                await close(1008)
                return
            text = message.get("text")
            if not isinstance(text, str) or len(text.encode("utf-8")) > 1024:
                await close(1009 if text else 1008)
                return
            try:
                subscription = Subscribe.model_validate(
                    json.loads(text, object_pairs_hook=unique_fields)
                )
            except ValueError:
                await close(1008)
                return
            if subscription.game_id.root != str(game_id):
                await close(1008)
                return
            cursor, bootstrap = subscription.after_seq, subscription.after_seq == 0
            # Consume disconnects concurrently with bounded SQL tailing. No second
            # subscription or write message is permitted on this read-only stream.
            receiver = asyncio.create_task(socket.receive())
            if wakeups is not None:
                wake = wakeups.register(game_id)
            while True:
                if receiver.done():
                    incoming = receiver.result()
                    if incoming["type"] != "websocket.disconnect":
                        await close(1008)
                    else:
                        code = incoming.get("code")
                        record_close(
                            code
                            if code
                            in {
                                1000,
                                1001,
                                1002,
                                1003,
                                1006,
                                1007,
                                1008,
                                1009,
                                1011,
                                1012,
                                1013,
                            }
                            else 1006
                        )
                    return
                if wake is not None:
                    wake.clear()
                async with bounded_sql():
                    current = await auth.authenticate(token)
                    batch = (
                        await service.read(
                            game_id, record.user.id, cursor, bootstrap=bootstrap
                        )
                        if current is not None and current.user.id == record.user.id
                        else None
                    )
                if batch is None:
                    await close(4401)
                    return
                for frame in batch.frames:
                    async with asyncio.timeout(5):
                        await socket.send_json(frame)
                cursor, bootstrap = batch.cursor, False
                if batch.resync:
                    await close(1012)
                    return
                # Wait for a disconnect or the next durable poll; no per-client buffer.
                if batch.more or wake is None:
                    await asyncio.wait({receiver}, timeout=0 if batch.more else 0.5)
                else:
                    hint = asyncio.create_task(wake.wait())
                    try:
                        await asyncio.wait(
                            {receiver, hint},
                            timeout=0.5,
                            return_when=asyncio.FIRST_COMPLETED,
                        )
                    finally:
                        hint.cancel()
                        with suppress(asyncio.CancelledError):
                            await hint
        except PublicProblem as exc:
            await close(4403 if exc.status in {403, 404} else 1011)
        except TimeoutError:
            await close(1011)
        except (WebSocketDisconnect, OSError):
            record_close(1006)
        except Exception:
            # Do not print database URLs, cookies, payloads or raw exception text.
            with suppress(RuntimeError, OSError):
                await close(1011)
        finally:
            try:
                if receiver is not None:
                    receiver.cancel()
                    with suppress(
                        asyncio.CancelledError, WebSocketDisconnect, RuntimeError
                    ):
                        await receiver
            finally:
                if wake is not None:
                    wakeups.remove(game_id, wake)
                connections.release(record.user.id)
                record_close(1000)

    return router
