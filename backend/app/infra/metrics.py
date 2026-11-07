"""Small bounded in-process metrics primitives for request observability."""

from __future__ import annotations

from collections import Counter
from threading import Lock


class MetricsRegistry:
    """Thread-safe counters with a deliberately bounded label surface."""

    def __init__(self, *, max_series: int = 256):
        if max_series < 1:
            raise ValueError("max_series must be positive")
        self._max_series = max_series
        self._counters: Counter[tuple[str, tuple[tuple[str, str], ...]]] = Counter()
        self._lock = Lock()

    def increment(self, name: str, *, value: int = 1, **labels: str) -> None:
        if not name or value < 1:
            raise ValueError("metric name and positive value are required")
        key = (name, tuple(sorted((str(k), str(v)) for k, v in labels.items())))
        with self._lock:
            if key not in self._counters and len(self._counters) >= self._max_series:
                return
            self._counters[key] += value

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return {
                f"{name}{self._format_labels(labels)}": value
                for (name, labels), value in self._counters.items()
            }

    @staticmethod
    def _format_labels(labels: tuple[tuple[str, str], ...]) -> str:
        if not labels:
            return ""
        return "{" + ",".join(f'{key}="{value}"' for key, value in labels) + "}"
