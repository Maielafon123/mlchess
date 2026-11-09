"""Authenticated rated HTTP adapters over SQL matchmaking."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request
from pydantic import ConfigDict, model_validator

from backend.app.auth.dependencies import GameId, current_session, key, writer
from backend.app.auth.service import SessionRecord
from backend.app.infra.generated import contracts as dto
from backend.app.infra.problems import PublicProblem

router = APIRouter(tags=["matchmaking"])
Reader = Annotated[SessionRecord, Depends(current_session)]
Writer = Annotated[SessionRecord, Depends(writer)]
CommandKey = Annotated[str, Header(max_length=36)]


class JoinRequest(dto.JoinMatchV1):
    model_config = ConfigDict(extra="forbid", strict=True)

    @model_validator(mode="before")
    @classmethod
    def require_integer_version(cls, value):
        if isinstance(value, dict) and type(value.get("schema_version")) is not int:
            raise ValueError("Schema version must be a JSON integer")
        return value


def service(request):
    result = request.app.state.matchmaking_service
    if result is None:
        raise PublicProblem(503)
    return result


@router.get(
    "/api/v1/matchmaking/pools",
    response_model=dto.MatchPoolsV1,
    operation_id="listRatingPools",
)
async def pools(request: Request, record: Reader):
    return await service(request).pools(record.user.id)


@router.get(
    "/api/v1/matchmaking/current",
    response_model=dto.CurrentMatchV1,
    operation_id="getCurrentMatch",
)
async def current(request: Request, record: Reader):
    return await service(request).current(record.user.id)


@router.post(
    "/api/v1/matchmaking/tickets",
    status_code=201,
    response_model=dto.MatchTicketV1,
    operation_id="joinMatchmaking",
)
async def join(
    payload: JoinRequest, request: Request, record: Writer, idempotency_key: CommandKey
):
    return await service(request).join(
        record.user.id, key(request, idempotency_key), payload.pool.root
    )


@router.get(
    "/api/v1/matchmaking/tickets/{ticket_id}",
    response_model=dto.MatchTicketV1,
    operation_id="getMatchTicket",
)
async def get(ticket_id: GameId, request: Request, record: Reader):
    return await service(request).get(record.user.id, UUID(ticket_id))


@router.delete(
    "/api/v1/matchmaking/tickets/{ticket_id}",
    response_model=dto.MatchTicketV1,
    operation_id="cancelMatchTicket",
)
async def cancel(
    ticket_id: GameId, request: Request, record: Writer, idempotency_key: CommandKey
):
    return await service(request).cancel(
        record.user.id, key(request, idempotency_key), UUID(ticket_id)
    )


@router.get(
    "/api/v1/games/{id}/rating",
    response_model=dto.RatedGameV1,
    operation_id="getRatedGame",
)
async def rated_game(id: GameId, request: Request, record: Reader):
    return await service(request).rated_game(record.user.id, UUID(id))
