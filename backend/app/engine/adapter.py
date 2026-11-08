from __future__ import annotations

import hashlib
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import chess
import chess.engine


class EngineError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class EngineBudget:
    time_ms: int | None = None
    nodes: int | None = None
    depth: int | None = None

    def __post_init__(self) -> None:
        values = (self.time_ms, self.nodes, self.depth)
        if any(value is not None and type(value) is not int for value in values):
            raise ValueError("Engine bounds must be integers")
        if not any(value is not None for value in values):
            raise ValueError("At least one engine bound is required")
        if self.time_ms is not None and not 1 <= self.time_ms <= 120_000:
            raise ValueError("time_ms is outside the allowed range")
        if self.nodes is not None and not 1 <= self.nodes <= 10_000_000:
            raise ValueError("nodes is outside the allowed range")
        if self.depth is not None and not 1 <= self.depth <= 64:
            raise ValueError("depth is outside the allowed range")


@dataclass(frozen=True, slots=True)
class EngineScore:
    pov: Literal["white", "black"]
    cp: int | None = None
    mate: int | None = None

    def __post_init__(self) -> None:
        if (self.cp is None) == (self.mate is None):
            raise ValueError("Score must contain exactly one of cp or mate")


@dataclass(frozen=True, slots=True)
class EngineMove:
    uci: str
    score: EngineScore | None = None
    depth: int | None = None


@dataclass(frozen=True, slots=True)
class EngineLine:
    uci: str
    san: str
    pv_uci: tuple[str, ...]
    score: EngineScore
    depth: int | None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class UciEngineAdapter:
    """Synchronous worker-only adapter with bounded UCI startup and commands."""

    PROFILES = {"beginner": 0, "casual": 6, "club": 12, "strong": 20}

    def __init__(self, binary: Path, *, sha256: str | None = None) -> None:
        path = binary.resolve()
        if not path.is_file() or not os.access(path, os.X_OK):
            raise EngineError("Configured engine binary is unavailable")
        if sha256 is not None and sha256_file(path).lower() != sha256.lower():
            raise EngineError("Configured engine binary hash does not match")
        self.binary = path
        self._engine: chess.engine.SimpleEngine | None = None

    def _start(self) -> chess.engine.SimpleEngine:
        if self._engine is None:
            self._engine = chess.engine.SimpleEngine.popen_uci(
                [str(self.binary)], timeout=5.0, shell=False, stderr=subprocess.DEVNULL
            )
            options = {
                key: value
                for key, value in {"Threads": 1, "Hash": 32}.items()
                if key in self._engine.options
            }
            if "Use NNUE" in self._engine.options:
                options["Use NNUE"] = True
            self._engine.configure(options)
        return self._engine

    def identity(self) -> str:
        return self._start().id["name"]

    def stop(self) -> None:
        engine, self._engine = self._engine, None
        if engine is not None:
            try:
                engine.quit()
            except (TimeoutError, OSError, chess.engine.EngineError):
                pass
            finally:
                engine.close()

    @staticmethod
    def _board(position: str | chess.Board) -> chess.Board:
        try:
            board = (
                position.copy(stack=True)
                if isinstance(position, chess.Board)
                else chess.Board(position)
            )
        except ValueError:
            raise EngineError("Invalid engine position") from None
        if not board.is_valid() or board.is_game_over(claim_draw=False):
            raise EngineError("Engine position is invalid or finished")
        return board

    @staticmethod
    def _limit(budget: EngineBudget) -> chess.engine.Limit:
        return chess.engine.Limit(
            time=budget.time_ms / 1000 if budget.time_ms else None,
            depth=budget.depth,
            nodes=budget.nodes,
        )

    @staticmethod
    def _score(info: dict) -> EngineScore | None:
        score = info.get("score")
        if score is None:
            return None
        white = score.white()
        return (
            EngineScore("white", mate=white.mate())
            if white.is_mate()
            else EngineScore("white", cp=white.score())
        )

    def _configure(self, profile: str) -> chess.engine.SimpleEngine:
        if profile not in self.PROFILES:
            raise EngineError("Unknown server engine profile")
        engine = self._start()
        if "Skill Level" in engine.options:
            engine.configure({"Skill Level": self.PROFILES[profile]})
        return engine

    def choose_move(
        self, fen: str | chess.Board, *, budget: EngineBudget, profile: str = "strong"
    ) -> EngineMove:
        board = self._board(fen)
        try:
            result = self._configure(profile).play(
                board,
                self._limit(budget),
                info=chess.engine.INFO_SCORE | chess.engine.INFO_BASIC,
            )
            if result.move is None or result.move not in board.legal_moves:
                raise EngineError("Engine returned an illegal move")
            return EngineMove(
                board.uci(result.move),
                self._score(result.info),
                result.info.get("depth"),
            )
        except (TimeoutError, OSError, chess.engine.EngineError, EngineError):
            self.stop()
            raise EngineError("Engine command failed or timed out") from None

    def analyze(
        self, position: str | chess.Board, *, budget: EngineBudget, multipv: int = 3
    ) -> tuple[EngineLine, ...]:
        if type(multipv) is not int or not 1 <= multipv <= 3:
            raise EngineError("MultiPV is outside the server allowlist")
        board = self._board(position)
        try:
            infos = self._configure("strong").analyse(
                board,
                self._limit(budget),
                multipv=min(multipv, board.legal_moves.count()),
                info=chess.engine.INFO_SCORE
                | chess.engine.INFO_PV
                | chess.engine.INFO_BASIC,
            )
            lines = []
            for info in infos:
                pv, score = info.get("pv", []), self._score(info)
                if not pv or score is None:
                    raise EngineError("Engine analysis is incomplete")
                replay = board.copy(stack=True)
                for move in pv:
                    if move not in replay.legal_moves:
                        raise EngineError("Engine returned an illegal variation")
                    replay.push(move)
                lines.append(
                    EngineLine(
                        board.uci(pv[0]),
                        board.san(pv[0]),
                        tuple(move.uci() for move in pv),
                        score,
                        info.get("depth"),
                    )
                )
            return tuple(lines)
        except (TimeoutError, OSError, chess.engine.EngineError, EngineError):
            self.stop()
            raise EngineError("Engine analysis failed or timed out") from None
