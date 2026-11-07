from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID, uuid4


class StreamDenied(ValueError):
    pass


class CursorError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class GameEvent:
    game_id: UUID
    seq: int
    type: str
    payload: dict
    event_id: UUID = field(default_factory=uuid4)


@dataclass
class InMemoryEventStream:
    participants: dict[UUID, frozenset[UUID]] = field(default_factory=dict)
    events: dict[UUID, list[GameEvent]] = field(default_factory=dict)

    def authorize(self, game_id: UUID, actor_id: UUID) -> None:
        if actor_id not in self.participants.get(game_id, frozenset()):
            raise StreamDenied("actor is not a game participant")

    def append(self, game_id: UUID, event_type: str, payload: dict) -> GameEvent:
        items = self.events.setdefault(game_id, [])
        event = GameEvent(game_id, len(items) + 1, event_type, payload)
        items.append(event)
        return event

    def replay(self, game_id: UUID, *, after_seq: int) -> list[GameEvent]:
        items = self.events.get(game_id, [])
        if after_seq < 0 or after_seq > len(items):
            raise CursorError("cursor is outside the durable event range")
        return items[after_seq:]
