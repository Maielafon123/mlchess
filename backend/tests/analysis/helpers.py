"""Deterministic engine double: never available in production composition."""

from backend.app.engine.adapter import EngineLine, EngineScore

METADATA = {
    "name": "stockfish",
    "version": "test-double",
    "model_hash": "1" * 64,
    "binary_sha256": "2" * 64,
}


class AnalysisEngine:
    def analyze(self, board, *, budget, multipv):
        assert budget.time_ms <= 1000
        return tuple(
            EngineLine(
                move.uci(),
                board.san(move),
                (move.uci(),),
                EngineScore("white", cp=30),
                1,
            )
            for move in list(board.legal_moves)[:multipv]
        )


def submit(http, game, headers, *, key=None, **overrides):
    from uuid import uuid4

    return http.post(
        f"/api/v1/games/{game['id']}/analysis-requests",
        json={"ply": 1, "analysis_level": "quick", **overrides},
        headers={**headers, "Idempotency-Key": key or str(uuid4())},
    )


def move(http, game, headers, uci="e2e4", version=0):
    from uuid import uuid4

    response = http.post(
        f"/api/v1/games/{game['id']}/moves",
        json={"uci": uci, "expected_version": version, "client_move_id": str(uuid4())},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()["snapshot"]
