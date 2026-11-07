from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class AccessDenied(ValueError):
    pass


class GameMode(StrEnum):
    FRIEND = "friend"
    RATED = "rated"
    AI = "ai"
    COACH = "coach"


@dataclass(frozen=True, slots=True)
class AccessSnapshot:
    mode: GameMode
    status: str
    revision: int
    participant_ids: frozenset[UUID]


class AccessPolicy:
    @staticmethod
    def require_participant(snapshot: AccessSnapshot, actor_id: UUID) -> None:
        if actor_id not in snapshot.participant_ids:
            raise AccessDenied("actor is not a participant")

    @classmethod
    def require_takeback(cls, snapshot: AccessSnapshot, actor_id: UUID) -> None:
        cls.require_participant(snapshot, actor_id)
        if snapshot.mode not in {GameMode.AI, GameMode.COACH}:
            raise AccessDenied("takeback is unavailable for PvP games")
        if snapshot.status not in {"waiting", "active", "finished"}:
            raise AccessDenied("game is not available for takeback")

    @classmethod
    def require_analysis(cls, snapshot: AccessSnapshot, actor_id: UUID) -> None:
        cls.require_participant(snapshot, actor_id)
        if snapshot.status != "finished" and snapshot.mode in {
            GameMode.FRIEND,
            GameMode.RATED,
        }:
            raise AccessDenied("live PvP analysis is forbidden")

    @classmethod
    def require_coach(cls, snapshot: AccessSnapshot, actor_id: UUID) -> None:
        cls.require_participant(snapshot, actor_id)
        if snapshot.mode != GameMode.COACH:
            raise AccessDenied("coach is available only in coach games")
        if snapshot.status not in {"active", "finished"}:
            raise AccessDenied("coach is unavailable in this game state")
