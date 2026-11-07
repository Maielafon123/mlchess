"""ASGI request correlation, same-origin policy and sanitized failure boundary."""

from __future__ import annotations

import json
import logging
import time
from contextvars import ContextVar
from uuid import uuid4

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from backend.app.infra.problems import problem_response
from backend.app.infra.settings import Settings, canonical_origin

request_id_context: ContextVar[str | None] = ContextVar(
    "mlchess_request_id", default=None
)


class RequestLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        # Deliberate allowlist: no headers, cookies, query, path, body or exception repr.
        return json.dumps(
            {
                key: getattr(record, key, None)
                for key in ("event", "request_id", "method", "status", "duration_ms")
            },
            separators=(",", ":"),
        )


def default_request_logger() -> logging.Logger:
    logger = logging.getLogger("mlchess.http")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(RequestLogFormatter())
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


class SafeHTTPMiddleware:
    def __init__(self, app: ASGIApp, *, settings: Settings, logger: logging.Logger):
        self.app, self.settings, self.logger = app, settings, logger

    def rejection(self, scope: Scope) -> int | None:
        headers = scope.get("headers", [])
        hosts = [
            value.decode("latin1") for name, value in headers if name.lower() == b"host"
        ]
        origins = [
            value.decode("latin1")
            for name, value in headers
            if name.lower() == b"origin"
        ]
        if len(hosts) != 1 or len(origins) > 1:
            return 400
        scheme = self.settings.public_origin.split("://", 1)[0]
        try:
            if (
                canonical_origin(scheme + "://" + hosts[0])
                != self.settings.public_origin
            ):
                return 400
            if origins and (
                origins[0].endswith("/")
                or canonical_origin(origins[0]) != self.settings.public_origin
            ):
                return 403
        except ValueError:
            return 400 if not origins else 403
        if scope["method"] not in {"GET", "HEAD", "OPTIONS"} and not origins:
            return 403
        return None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request_id = str(uuid4())
        scope.setdefault("state", {})["request_id"] = request_id
        token = request_id_context.set(request_id)
        start = time.monotonic()
        started = completed = False
        status = 500
        event = "request.completed"

        async def safe_send(message: Message):
            nonlocal started, completed, status
            if message["type"] == "http.response.start":
                started = True
                status = message["status"]
                hidden = {
                    b"x-request-id",
                    b"access-control-allow-origin",
                    b"access-control-allow-credentials",
                    b"cache-control",
                    b"x-content-type-options",
                }
                headers = [
                    (key, value)
                    for key, value in message.get("headers", [])
                    if key.lower() not in hidden
                ]
                message = {
                    **message,
                    "headers": headers
                    + [
                        (b"x-request-id", request_id.encode("ascii")),
                        (b"cache-control", b"no-store"),
                        (b"x-content-type-options", b"nosniff"),
                    ],
                }
            elif message["type"] == "http.response.body" and not message.get(
                "more_body", False
            ):
                completed = True
            await send(message)

        try:
            rejected = self.rejection(scope)
            if rejected:
                await problem_response(rejected, request_id)(scope, receive, safe_send)
            else:
                await self.app(scope, receive, safe_send)
        except Exception:
            event = "request.failed"
            if not started:
                await problem_response(500, request_id)(scope, receive, safe_send)
            elif not completed:
                # Cannot change a committed status. Close a partial stream without
                # propagating exception text to the ASGI server logger.
                try:
                    await safe_send(
                        {"type": "http.response.body", "body": b"", "more_body": False}
                    )
                except Exception:
                    pass  # Disconnected client: there is no safe response recipient.
        finally:
            method = (
                scope["method"]
                if scope["method"]
                in {"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"}
                else "OTHER"
            )
            try:
                self.logger.info(
                    event,
                    extra={
                        "event": event,
                        "request_id": request_id,
                        "method": method,
                        "status": status,
                        "duration_ms": max(0, int((time.monotonic() - start) * 1000)),
                    },
                )
            finally:
                request_id_context.reset(token)
