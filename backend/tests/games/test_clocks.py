from datetime import datetime, timedelta, timezone

import chess
import pytest

from backend.app.games.clocks import ServerClock


def test_clock_uses_server_anchor_and_increment():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    clock = ServerClock(10_000, 10_000, 500, chess.WHITE, start)
    now = start + timedelta(seconds=2)
    assert clock.remaining(chess.WHITE, now=now) == 8_000
    updated = clock.after_legal_move(actor=chess.WHITE, server_now=now)
    assert updated.white_remaining_ms == 8_500
    assert updated.running_side is chess.BLACK


def test_flag_fall_never_returns_negative_time():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    clock = ServerClock(100, 0, running_side=chess.WHITE, anchor=start)
    assert (
        clock.before_command(
            actor=chess.WHITE, server_now=start + timedelta(seconds=1)
        ).winner
        is None
    )
    with pytest.raises(ValueError):
        ServerClock(-1, 0)
