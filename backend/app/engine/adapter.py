from __future__ import annotations

import hashlib
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


class EngineError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class EngineBudget:
    time_ms: int | None = None
    nodes: int | None = None
    depth: int | None = None

    def __post_init__(self) -> None:
        values = (self.time_ms, self.nodes, self.depth)
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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class UciEngineAdapter:
    def __init__(self, binary: Path, *, sha256: str | None = None) -> None:
        path = binary.resolve()
        if not path.is_file() or not os.access(path, os.X_OK):
            raise EngineError("Configured engine binary is unavailable")
        if sha256 is not None and sha256_file(path).lower() != sha256.lower():
            raise EngineError("Configured engine binary hash does not match")
        self.binary = path
        self._process: subprocess.Popen[str] | None = None

    def _start(self) -> subprocess.Popen[str]:
        process = subprocess.Popen(
            [str(self.binary)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
            shell=False,
        )
        self._process = process
        self._send("uci")
        self._read_until("uciok")
        self._send("isready")
        self._read_until("readyok")
        return process

    def _send(self, command: str) -> None:
        if self._process is None or self._process.stdin is None:
            raise EngineError("Engine is not running")
        self._process.stdin.write(command + "\n")
        self._process.stdin.flush()

    def _read_until(self, marker: str) -> list[str]:
        if self._process is None or self._process.stdout is None:
            raise EngineError("Engine is not running")
        lines: list[str] = []
        for line in self._process.stdout:
            line = line.strip()
            lines.append(line)
            if line == marker:
                return lines
        raise EngineError("Engine exited before completing UCI command")

    def stop(self) -> None:
        if self._process is not None:
            try:
                self._send("quit")
                self._process.wait(timeout=1)
            except (OSError, subprocess.TimeoutExpired):
                self._process.kill()
            finally:
                self._process = None

    def choose_move(self, fen: str, *, budget: EngineBudget) -> EngineMove:
        process = self._process or self._start()
        self._send(f"position fen {fen}")
        limits = []
        if budget.time_ms is not None:
            limits.append(f"movetime {budget.time_ms}")
        if budget.nodes is not None:
            limits.append(f"nodes {budget.nodes}")
        if budget.depth is not None:
            limits.append(f"depth {budget.depth}")
        self._send("go " + " ".join(limits))
        if process.stdout is None:
            raise EngineError("Engine output is unavailable")
        for line in process.stdout:
            line = line.strip()
            if line.startswith("bestmove "):
                move = line.split()[1]
                if not re.fullmatch(r"[a-h][1-8][a-h][1-8][qrbn]?", move):
                    raise EngineError("Engine returned malformed UCI move")
                return EngineMove(move)
        raise EngineError("Engine exited without bestmove")
