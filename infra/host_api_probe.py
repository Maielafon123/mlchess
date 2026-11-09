"""Readiness for the host-network VPS API, without inspecting host networking."""

import os
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


def main() -> int:
    try:
        port = int(os.environ.get("MLCHESS_PROBE_PORT", "58000"))
        if port not in {58000, 58120}:
            return 1
        request = Request(
            f"http://127.0.0.1:{port}/health/ready",
            headers={"Host": urlsplit(os.environ["MLCHESS_PUBLIC_ORIGIN"]).netloc},
        )
        with urlopen(request, timeout=3) as response:
            return 0 if response.status == 200 else 1
    except Exception:
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
