from __future__ import annotations

import re
import time
from collections import defaultdict, deque
from dataclasses import dataclass


class RateLimitExceeded(Exception):
    pass


@dataclass
class SlidingWindowLimiter:
    limit: int
    window_seconds: float

    def __post_init__(self) -> None:
        if self.limit < 1 or self.window_seconds <= 0:
            raise ValueError("invalid limiter configuration")
        self._events: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str, *, now: float | None = None) -> None:
        current = time.monotonic() if now is None else now
        events = self._events[key]
        cutoff = current - self.window_seconds
        while events and events[0] <= cutoff:
            events.popleft()
        if len(events) >= self.limit:
            raise RateLimitExceeded
        events.append(current)


_SECRET_PATTERNS = (
    re.compile(r"(?i)(password|token|secret|authorization)=(?:Bearer\s+)?[^&\s]+"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._-]+"),
)


def redact(value: str) -> str:
    result = value
    for pattern in _SECRET_PATTERNS:
        result = pattern.sub(
            lambda match: (
                match.group(1) + "=<redacted>"
                if "=" in match.group(0)
                else "Bearer <redacted>"
            ),
            result,
        )
    return result
