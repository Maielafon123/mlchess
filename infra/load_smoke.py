"""Check a small burst of isolated guest sessions against private Compose."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from http.cookiejar import CookieJar
import json
from time import monotonic
from urllib.parse import urlsplit
from urllib.request import HTTPCookieProcessor, Request, build_opener


def visitor(origin):
    client = build_opener(HTTPCookieProcessor(CookieJar()))

    def fetch(path, *, post=False):
        started = monotonic()
        request = Request(
            origin + path,
            data=b"{}" if post else None,
            headers={"Origin": origin, "Content-Type": "application/json"}
            if post
            else {},
        )
        with client.open(request, timeout=8) as response:
            if response.status != 200:
                raise RuntimeError("Unexpected response status")
            payload = json.loads(response.read(65537))
        return payload, monotonic() - started

    guest, _ = fetch("/api/v1/auth/guest", post=True)
    if guest["kind"] != "guest":
        raise RuntimeError("Expected isolated guest session")
    elapsed = []
    for _ in range(4):
        me, auth_time = fetch("/api/v1/me")
        progress, learn_time = fetch("/api/v1/learning/progress")
        if me["id"] != guest["id"] or progress["student_id"] != guest["id"]:
            raise RuntimeError("A response belonged to a different session")
        elapsed.extend((auth_time, learn_time))
    return guest["id"], elapsed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--origin", required=True)
    args = parser.parse_args()
    origin = urlsplit(args.origin)
    if (
        origin.scheme != "http"
        or origin.hostname not in {"localhost", "127.0.0.1"}
        or origin.username
        or origin.password
        or origin.query
        or origin.fragment
        or origin.path
        or not origin.port
        or origin.port < 1024
    ):
        parser.error("Use a private loopback Compose origin")
    with ThreadPoolExecutor(max_workers=8) as workers:
        results = list(workers.map(visitor, [args.origin] * 8))
    if len({actor for actor, _ in results}) != 8:
        raise RuntimeError("Guest sessions were not isolated")
    times = sorted(time for _, samples in results for time in samples)
    print(
        json.dumps(
            {
                "status": "pass",
                "scope": "local Compose burst, not production capacity",
                "guests": len(results),
                "authenticated_reads": len(times),
                "p95_ms": round(times[(len(times) * 95 - 1) // 100] * 1000),
                "max_ms": round(times[-1] * 1000),
            }
        )
    )


if __name__ == "__main__":
    main()
