"""Authenticated, CSRF-protected command adapters over durable game transactions."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request
from pydantic import ConfigDict, model_validator

from backend.app.auth.dependencies import GameId, current_session, key, writer
from backend.app.auth.service import SessionRecord
from backend.app.infra.generated.contracts import (
    CreateGameV1,
    GameActionV1,
    GameActionsV1,
    GameSnapshotV1,
    MoveAcceptedV1,
    SubmitMoveV1,
    TakebackV1,
)
from backend.app.infra.problems import PublicProblem

router = APIRouter(prefix="/api/v1/games", tags=["games"])


class CreateRequest(CreateGameV1):
    model_config = ConfigDict(extra="forbid", strict=True)

    @model_validator(mode="before")
    @classmethod
    def conditional_fields(cls, data):
        if not isinstance(data, dict) or "time_control" not in data:
            raise ValueError("time_control must be explicit")
        if data.get("mode") == "friend":
            if "human_color" in data or "ai_profile" in data:
                raise ValueError("Solo configuration is not valid for friend games")
        elif data.get("mode") in {"ai", "coach"}:
            if not data.get("human_color") or not data.get("ai_profile"):
                raise ValueError("Solo configuration is required")
        tc = data.get("time_control")
        if tc is not None and (
            not isinstance(tc, dict)
            or any(type(tc.get(k)) is not int for k in ("initial_ms", "increment_ms"))
        ):
            raise ValueError("Clock values must be JSON integers")
        return data


class MoveRequest(SubmitMoveV1):
    model_config = ConfigDict(extra="forbid", strict=True)


class TakebackRequest(TakebackV1):
    model_config = ConfigDict(extra="forbid", strict=True)

    @model_validator(mode="before")
    @classmethod
    def integer_plies(cls, data):
        if isinstance(data, dict) and type(data.get("plies")) is not int:
            raise ValueError("plies must be a JSON integer")
        return data


class ActionRequest(GameActionV1):
    model_config = ConfigDict(extra="forbid", strict=True)


def service(request: Request):
    result = request.app.state.game_service
    if result is None:
        raise PublicProblem(503)
    return result


@router.post(
    "", status_code=201, response_model=GameSnapshotV1, operation_id="createGame"
)
async def create_game(
    payload: CreateRequest,
    request: Request,
    record: Annotated[SessionRecord, Depends(writer)],
    idempotency_key: Annotated[str, Header(max_length=36)],
):
    return await service(request).create(
        record.user.id,
        key(request, idempotency_key),
        payload.model_dump(mode="json", exclude_unset=True),
    )


@router.get("/{id}", response_model=GameSnapshotV1, operation_id="getGame")
async def get_game(
    id: GameId,
    request: Request,
    record: Annotated[SessionRecord, Depends(current_session)],
):
    return await service(request).get(UUID(id), record.user.id)


@router.get(
    "/{id}/actions", response_model=GameActionsV1, operation_id="getGameActions"
)
async def game_actions(
    id: GameId,
    request: Request,
    record: Annotated[SessionRecord, Depends(current_session)],
):
    return await service(request).actions(UUID(id), record.user.id)


@router.post("/{id}/moves", response_model=MoveAcceptedV1, operation_id="submitMove")
async def move(
    id: GameId,
    payload: MoveRequest,
    request: Request,
    record: Annotated[SessionRecord, Depends(writer)],
):
    return await service(request).command(
        UUID(id),
        record.user.id,
        UUID(payload.client_move_id.root),
        "move",
        payload.model_dump(mode="json"),
    )


@router.post(
    "/{id}/takeback", response_model=GameSnapshotV1, operation_id="takebackGame"
)
async def takeback(
    id: GameId,
    payload: TakebackRequest,
    request: Request,
    record: Annotated[SessionRecord, Depends(writer)],
):
    return await service(request).command(
        UUID(id),
        record.user.id,
        UUID(payload.client_action_id.root),
        "takeback",
        payload.model_dump(mode="json"),
    )


def register_action(path: str, operation: str, operation_id: str):
    async def action(
        id: GameId,
        payload: ActionRequest,
        request: Request,
        record: Annotated[SessionRecord, Depends(writer)],
        idempotency_key: Annotated[str, Header(max_length=36)],
    ):
        return await service(request).command(
            UUID(id),
            record.user.id,
            key(request, idempotency_key),
            operation,
            payload.model_dump(mode="json"),
        )

    router.add_api_route(
        "/{id}/" + path,
        action,
        methods=["POST"],
        response_model=GameSnapshotV1,
        operation_id=operation_id,
    )


register_action("resign", "resign", "resignGame")
register_action("draw-offers", "draw-offer", "offerDraw")
register_action("draw-offers/accept", "accept-draw", "acceptDraw")
register_action("claim-draw", "claim-draw", "claimDraw")
