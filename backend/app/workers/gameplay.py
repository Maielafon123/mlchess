from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from backend.app.games.domain import GameDomain


@dataclass(frozen=True, slots=True)
class EngineMoveJob:
    game_id: UUID
    revision: int
    expected_version: int
    engine_side: bool
    move_uci: str


def can_apply_engine_job(snapshot: GameDomain, job: EngineMoveJob) -> bool:
    """CAS guard checked immediately before applying a worker result."""
    return (
        snapshot.status == "active"
        and snapshot.revision == job.revision
        and snapshot.version == job.expected_version
        and snapshot.side_to_move == job.engine_side
    )
