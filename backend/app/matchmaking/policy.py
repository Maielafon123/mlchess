"""Fixed queue pools and the versioned rated policy; clients supply only pool IDs."""

POOLS = {
    "rapid-10+0": {"initial_ms": 600_000, "increment_ms": 0},
    "blitz-5+0": {"initial_ms": 300_000, "increment_ms": 0},
}
START_RATING = 1200
MIN_RATING = 100
MAX_RATING = 4000
RATING_RADIUS = 400
TICKET_SECONDS = 120


def elo_delta(white: int, black: int, outcome: str, *, k: int = 32) -> int:
    expected = 1 / (1 + 10 ** ((black - white) / 400))
    actual = {"white": 1.0, "black": 0.0, "draw": 0.5}[outcome]
    return round(k * (actual - expected))


def bounded_delta(white: int, black: int, outcome: str) -> int:
    delta = elo_delta(white, black, outcome)
    return (
        min(delta, MAX_RATING - white, black - MIN_RATING)
        if delta >= 0
        else max(delta, MIN_RATING - white, black - MAX_RATING)
    )
