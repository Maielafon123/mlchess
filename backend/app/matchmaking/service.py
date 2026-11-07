from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from uuid import UUID, uuid4


class TicketStatus(StrEnum):
    SEARCHING = "searching"
    MATCHED = "matched"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class MatchmakingError(ValueError):
    pass


@dataclass
class Ticket:
    id: UUID
    user_id: UUID
    time_control: str
    rating_pool: str
    created_at: datetime
    expires_at: datetime
    status: TicketStatus = TicketStatus.SEARCHING
    game_id: UUID | None = None


class InMemoryMatchmaker:
    def __init__(self, *, ttl_seconds: int = 120) -> None:
        if not 10 <= ttl_seconds <= 3600:
            raise ValueError("ticket TTL is outside allowed range")
        self.ttl_seconds = ttl_seconds
        self.tickets: dict[UUID, Ticket] = {}

    def create(
        self,
        *,
        user_id: UUID,
        time_control: str,
        rating_pool: str,
        now: datetime | None = None,
    ) -> Ticket:
        now = now or datetime.now(timezone.utc)
        self.expire(now=now)
        if any(
            ticket.user_id == user_id and ticket.status == TicketStatus.SEARCHING
            for ticket in self.tickets.values()
        ):
            raise MatchmakingError("user already has a searching ticket")
        ticket = Ticket(
            uuid4(),
            user_id,
            time_control,
            rating_pool,
            now,
            now + timedelta(seconds=self.ttl_seconds),
        )
        self.tickets[ticket.id] = ticket
        return ticket

    def cancel(self, ticket_id: UUID, *, user_id: UUID) -> Ticket:
        ticket = self._owned(ticket_id, user_id)
        if ticket.status != TicketStatus.SEARCHING:
            raise MatchmakingError("ticket is no longer searching")
        ticket.status = TicketStatus.CANCELLED
        return ticket

    def match(
        self, *, now: datetime | None = None
    ) -> tuple[Ticket, Ticket, UUID] | None:
        now = now or datetime.now(timezone.utc)
        self.expire(now=now)
        candidates = [
            t for t in self.tickets.values() if t.status == TicketStatus.SEARCHING
        ]
        for index, first in enumerate(candidates):
            for second in candidates[index + 1 :]:
                if first.user_id == second.user_id:
                    continue
                if (first.time_control, first.rating_pool) != (
                    second.time_control,
                    second.rating_pool,
                ):
                    continue
                game_id = uuid4()
                first.status = second.status = TicketStatus.MATCHED
                first.game_id = second.game_id = game_id
                return first, second, game_id
        return None

    def expire(self, *, now: datetime) -> None:
        for ticket in self.tickets.values():
            if ticket.status == TicketStatus.SEARCHING and ticket.expires_at <= now:
                ticket.status = TicketStatus.EXPIRED

    def _owned(self, ticket_id: UUID, user_id: UUID) -> Ticket:
        ticket = self.tickets.get(ticket_id)
        if ticket is None or ticket.user_id != user_id:
            raise MatchmakingError("ticket is not available")
        return ticket
