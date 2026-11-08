"""Original CC BY 4.0 learning seed; production installs the frozen migration copy."""

import hashlib
import json
from pathlib import Path

import chess
from sqlalchemy import select

from backend.app.infra.models import LessonRow, PuzzleRow


def load_catalog():
    data = json.loads(
        Path(__file__).with_name("catalog.json").read_text(encoding="utf-8")
    )
    for puzzle in data["puzzles"]:
        board = chess.Board(puzzle["fen"])
        if not board.is_valid() or board.fen() != puzzle["fen"]:
            raise ValueError("Curated puzzle position is invalid")
        expected = hashlib.sha256(
            (puzzle["fen"] + "|" + " ".join(puzzle["private_solution"])).encode()
        ).hexdigest()
        if expected != puzzle["solution_digest"]:
            raise ValueError("Curated puzzle digest is invalid")
        for uci in puzzle["private_solution"]:
            board.push_uci(uci)
        if "mate" in puzzle["tags"] and not board.is_checkmate():
            raise ValueError("Curated mate puzzle does not end in mate")
    return data


async def seed_test_catalog(factory):
    """Explicit test helper. Production content is installed only by Alembic."""
    data = load_catalog()
    async with factory() as session, session.begin():
        for model, key in ((LessonRow, "lessons"), (PuzzleRow, "puzzles")):
            for row in data[key]:
                if (
                    await session.scalar(select(model.id).where(model.id == row["id"]))
                    is None
                ):
                    session.add(model(**row))
