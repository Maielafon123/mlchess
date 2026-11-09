"""An existing timed game gains an index without rewriting its clock history."""

import json
import sqlite3
from uuid import uuid4

import chess
from alembic import command
from alembic.config import Config


def test_upgrade_indexes_only_running_legacy_clocks(tmp_path):
    path = tmp_path / "legacy.db"
    config = Config("backend/alembic.ini")
    config.attributes["ignore_environment_url"] = True
    config.set_main_option("sqlalchemy.url", "sqlite+aiosqlite:///" + path.as_posix())
    command.upgrade(config, "0005_learning")
    anchor = "2026-01-01T12:00:00Z"
    cases = [
        ("active", True, "2026-01-01 12:00:01.250"),
        ("active", False, "2026-01-01 12:00:02.500"),
        ("waiting", None, None),
        ("finished", None, None),
    ]
    rows = []
    with sqlite3.connect(path) as db:
        for status, side, expected in cases:
            game_id = uuid4().hex
            clock = json.dumps(
                {
                    "white_remaining_ms": 1250,
                    "black_remaining_ms": 2500,
                    "increment_ms": 0,
                    "running_side": side,
                    "anchor": anchor,
                }
            )
            db.execute(
                "INSERT INTO games(id,mode,status,version,revision,fen,ply,side_to_move,created_at,updated_at) VALUES(?, 'friend', ?, 0, 0, ?, 0, 'white', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
                (game_id, status, chess.STARTING_FEN),
            )
            db.execute(
                "INSERT INTO game_states(game_id,domain,config,clock,event_seq) VALUES(?, '{}', '{}', ?, 0)",
                (game_id, clock),
            )
            rows.append((game_id, clock, expected))
    command.upgrade(config, "head")
    with sqlite3.connect(path) as db:
        for game_id, clock, expected in rows:
            observed = db.execute(
                "SELECT games.clock_deadline_at, game_states.clock, game_states.clock_observed_at FROM games JOIN game_states ON games.id=game_states.game_id WHERE games.id=?",
                (game_id,),
            ).fetchone()
            assert observed == (expected, clock, "2026-01-01 12:00:00.000")
