from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request
from pydantic import ConfigDict

from backend.app.auth.service import SessionRecord
from backend.app.auth.dependencies import GameId, current_session, key, writer
from backend.app.infra.generated.contracts import (
    AcceptInvitationV1,
    CreateInvitationV1,
    InviteSnapshotV1,
)
from backend.app.infra.problems import PublicProblem

router = APIRouter(prefix="/api/v1/invitations", tags=["invitations"])


class CreateRequest(CreateInvitationV1):
    model_config = ConfigDict(extra="forbid", strict=True)


class AcceptRequest(AcceptInvitationV1):
    model_config = ConfigDict(extra="forbid", strict=True)


def service(request):
    value = request.app.state.invitation_service
    if value is None:
        raise PublicProblem(503)
    return value


@router.post(
    "",
    status_code=201,
    response_model=InviteSnapshotV1,
    operation_id="createInvitation",
)
async def create(
    payload: CreateRequest,
    request: Request,
    record: Annotated[SessionRecord, Depends(writer)],
    idempotency_key: Annotated[str, Header(max_length=36)],
):
    return await service(request).create(
        record.user.id, key(request, idempotency_key), UUID(payload.game_id.root)
    )


@router.get("/{id}", response_model=InviteSnapshotV1, operation_id="getInvitation")
async def get(
    id: GameId,
    request: Request,
    record: Annotated[SessionRecord, Depends(current_session)],
):
    return await service(request).get(record.user.id, UUID(id))


@router.post(
    "/{id}/accept", response_model=InviteSnapshotV1, operation_id="acceptInvitation"
)
async def accept(
    id: GameId,
    payload: AcceptRequest,
    request: Request,
    record: Annotated[SessionRecord, Depends(writer)],
    idempotency_key: Annotated[str, Header(max_length=36)],
):
    return await service(request).accept(
        record.user.id, key(request, idempotency_key), UUID(id), payload.token
    )
