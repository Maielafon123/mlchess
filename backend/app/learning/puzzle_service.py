"""Server-side puzzle grading boundary (B-020)."""

from dataclasses import dataclass, field
from typing import Literal

import chess


@dataclass(frozen=True)
class Puzzle:
    id: str
    fen: str
    solution_uci: tuple[str, ...]
    difficulty: int
    tags: tuple[str, ...]
    source_name: str
    source_url: str
    license: str


@dataclass
class PuzzleSession:
    puzzle: Puzzle
    board: chess.Board = field(init=False)
    solution_index: int = 0
    attempts: dict[str, dict] = field(default_factory=dict)

    def __post_init__(self):
        self.board = chess.Board(self.puzzle.fen)


class PuzzleGrader:
    def __init__(self, puzzles: dict[str, Puzzle]):
        self.puzzles = puzzles
        self.sessions: dict[tuple[str, str], PuzzleSession] = {}

    def start(self, user_id: str, puzzle_id: str) -> PuzzleSession:
        puzzle = self.puzzles[puzzle_id]
        return self.sessions.setdefault((user_id, puzzle_id), PuzzleSession(puzzle))

    def submit(self, user_id: str, puzzle_id: str, *, attempt_id: str, uci: str, is_correct: bool | None = None) -> dict:
        session = self.start(user_id, puzzle_id)
        if attempt_id in session.attempts:
            return session.attempts[attempt_id]
        if session.solution_index >= len(session.puzzle.solution_uci):
            response = {"schema_version": 1, "attempt_id": attempt_id, "result": "completed", "completed": True, "next_ply": session.solution_index, "difficulty": session.puzzle.difficulty, "tags": list(session.puzzle.tags)}
            session.attempts[attempt_id] = response
            return response
        result: Literal["correct", "incorrect", "illegal"]
        if not self._is_legal(session.board, uci):
            result = "illegal"
        elif uci != session.puzzle.solution_uci[session.solution_index]:
            result = "incorrect"
        else:
            result = "correct"
            session.board.push_uci(uci)
            session.solution_index += 1
        response = {"schema_version": 1, "attempt_id": attempt_id, "result": result, "completed": session.solution_index == len(session.puzzle.solution_uci), "next_ply": session.solution_index, "difficulty": session.puzzle.difficulty, "tags": list(session.puzzle.tags)}
        session.attempts[attempt_id] = response
        return response

    @staticmethod
    def _is_legal(board: chess.Board, uci: str) -> bool:
        try:
            move = chess.Move.from_uci(uci)
        except ValueError:
            return False
        return move in board.legal_moves


CURATED_PUZZLES = {
    "back-rank": Puzzle(
        id="back-rank", fen="6k1/5ppp/8/8/8/8/5PPP/3R2K1 w - - 0 1",
        solution_uci=("d1d8",), difficulty=1, tags=("mate", "back-rank"),
        source_name="MLChess curated", source_url="https://mlchess.dev/puzzles/back-rank", license="CC BY 4.0",
    ),
}
