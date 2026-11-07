"""Generate learning exercises only from verified post-game analysis (B-023)."""

from dataclasses import dataclass

import chess

from .puzzle_service import Puzzle, CURATED_PUZZLES


@dataclass(frozen=True)
class VerifiedMistake:
    game_id: str
    owner_id: str
    revision: int
    fen: str
    motif: str | None
    motif_verified: bool
    source_mode: str
    solution_uci: tuple[str, ...]


class ExerciseService:
    def __init__(self, curated: dict[str, Puzzle] | None = None):
        self.curated = curated or CURATED_PUZZLES
        self.generated: dict[str, Puzzle] = {}

    def from_mistake(self, student_id: str, mistake: VerifiedMistake) -> Puzzle | None:
        if mistake.owner_id != student_id or mistake.source_mode != "pvp" or not mistake.motif_verified or not mistake.motif:
            return None
        if not self._legal_line(mistake.fen, mistake.solution_uci):
            return None
        key = f"{mistake.game_id}:{mistake.revision}:{mistake.motif}"
        if key in self.generated:
            return self.generated[key]
        puzzle = Puzzle(key, mistake.fen, mistake.solution_uci, 2, (mistake.motif,), "MLChess verified game", f"https://mlchess.dev/games/{mistake.game_id}", "User-owned derived content")
        self.generated[key] = puzzle
        return puzzle

    def fallback(self) -> Puzzle:
        return next(iter(self.curated.values()))

    @staticmethod
    def _legal_line(fen: str, line: tuple[str, ...]) -> bool:
        try:
            board = chess.Board(fen)
            for uci in line:
                board.push_uci(uci)
            return bool(line)
        except ValueError:
            return False
