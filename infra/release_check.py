"""Audit the composed application surface; nonzero means release is blocked.

This local preflight deliberately does not treat unit tests or registered route
names as evidence that staging, durability, recovery or two-browser E2E passed.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

from fastapi import FastAPI
from starlette.routing import Match

from backend.app.infra.settings import Settings
from backend.app.main import create_app


REQUIRED_HTTP = {
    ("GET", "/api/v1/me"),
    ("GET", "/api/v1/auth/providers"),
    ("POST", "/api/v1/auth/oidc/start"),
    ("GET", "/api/v1/auth/oidc/callback"),
    ("POST", "/api/v1/games"),
    ("GET", "/api/v1/games/{game_id}"),
    ("POST", "/api/v1/games/{game_id}/moves"),
    ("POST", "/api/v1/games/{game_id}/takeback"),
    ("POST", "/api/v1/games/{game_id}/resign"),
    ("POST", "/api/v1/games/{game_id}/draw-offers"),
    ("POST", "/api/v1/games/{game_id}/draw-offers/accept"),
    ("POST", "/api/v1/games/{game_id}/claim-draw"),
    ("POST", "/api/v1/invitations"),
    ("POST", "/api/v1/invitations/{code}/accept"),
    ("POST", "/api/v1/matchmaking/tickets"),
    ("GET", "/api/v1/matchmaking/tickets/{ticket_id}"),
    ("DELETE", "/api/v1/matchmaking/tickets/{ticket_id}"),
    ("GET", "/api/v1/matchmaking/current"),
    ("GET", "/api/v1/matchmaking/pools"),
    ("GET", "/api/v1/games/{game_id}/rating"),
    ("GET", "/api/v1/games/{game_id}/actions"),
    ("POST", "/api/v1/games/{game_id}/analysis-requests"),
    ("GET", "/api/v1/games/{game_id}/analysis/{ply}"),
    ("POST", "/api/v1/games/{game_id}/coach-requests"),
    ("GET", "/api/v1/games/{game_id}/coach-requests/{job_id}"),
    ("GET", "/api/v1/learning/lessons"),
    ("POST", "/api/v1/learning/puzzles/{puzzle_id}/attempts"),
    ("GET", "/api/v1/learning/progress"),
    ("GET", "/api/v1/learning/context"),
    ("GET", "/api/v1/learning/lessons/{id}"),
    ("POST", "/api/v1/learning/lessons/{id}/status"),
    ("GET", "/api/v1/learning/puzzles"),
    ("GET", "/api/v1/learning/puzzles/{id}"),
    ("GET", "/api/v1/learning/puzzles/{id}/state"),
    ("POST", "/api/v1/learning/puzzles/{id}/hints"),
    ("POST", "/api/v1/learning/puzzles/{id}/restart"),
    ("GET", "/api/v1/learning/review-queue"),
    ("GET", "/api/v1/learning/export"),
    ("DELETE", "/api/v1/learning/data"),
}
REQUIRED_WS = {"/ws/v1/games/{game_id}"}


def normalize_path(path: str) -> str:
    """Parameter names differ between implementations; route structure matters."""
    return re.sub(r"\{[^{}]+\}", "{}", path)


def has_websocket(app, path: str) -> bool:
    scope = {
        "type": "websocket",
        "path": normalize_path(path).replace(
            "{}", "00000000-0000-4000-8000-000000000001"
        ),
        "root_path": "",
        "headers": [],
    }
    return any(route.matches(scope)[0] is Match.FULL for route in app.routes)


def audit_routes(app: FastAPI) -> dict:
    # Included routers need not be flattened in FastAPI's public route list.
    http = {
        (method.upper(), normalize_path(path))
        for path, operations in app.openapi()["paths"].items()
        for method in operations
    }
    missing_http = sorted(
        f"{method} {path}"
        for method, path in REQUIRED_HTTP
        if (method, normalize_path(path)) not in http
    )
    missing_ws = sorted(path for path in REQUIRED_WS if not has_websocket(app, path))
    return {
        "status": "blocked" if missing_http or missing_ws else "surface-present",
        "missing_http": missing_http,
        "missing_websockets": missing_ws,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Write a local JSON report")
    args = parser.parse_args()
    app = create_app(Settings(environment="test", public_origin="http://testserver"))
    report = audit_routes(app)
    report["scope"] = "local route preflight, not production sign-off"
    report["remaining_evidence"] = [
        "PostgreSQL transactional command races and restart durability",
        "A+B staging E2E: four modes, learning, two-browser PvP",
        "Real queue/worker recovery and pinned Stockfish integration",
        "Backup restore rehearsal and measured RPO/RTO",
        "Supply-chain/license inventory and deployment configuration checks",
    ]
    rendered = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 1 if report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
