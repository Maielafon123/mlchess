"""Strict v1 analysis HTTP adapter; no engine invocation in the API process."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Path, Request
from pydantic import ConfigDict, model_validator
from starlette.responses import JSONResponse

from backend.app.auth.dependencies import GameId, current_session, key, writer
from backend.app.auth.service import SessionRecord
from backend.app.infra.generated.contracts import (
    AnalysisRequestV1,
    AnalysisJobV1,
    AnalysisResultV1,
)
from backend.app.infra.problems import PublicProblem

router = APIRouter(prefix="/api/v1/games", tags=["analysis"])


class AnalysisRequest(AnalysisRequestV1):
    model_config = ConfigDict(extra="forbid", strict=True)

    @model_validator(mode="before")
    @classmethod
    def integer_ply(cls, data):
        if isinstance(data, dict) and type(data.get("ply")) is not int:
            raise ValueError("ply must be a JSON integer")
        return data


def service(request):
    if request.app.state.analysis_service is None:
        raise PublicProblem(503)
    return request.app.state.analysis_service


@router.post(
    "/{id}/analysis-requests",
    status_code=202,
    response_model=AnalysisJobV1,
    operation_id="requestAnalysis",
)
async def submit(
    id: GameId,
    payload: AnalysisRequest,
    request: Request,
    record: Annotated[SessionRecord, Depends(writer)],
    idempotency_key: Annotated[str, Header(max_length=36)],
):
    return await service(request).submit(
        UUID(id),
        record.user.id,
        key(request, idempotency_key),
        payload.model_dump(mode="json"),
    )


@router.get(
    "/{id}/analysis/{ply}",
    response_model=AnalysisResultV1,
    operation_id="getAnalysis",
    responses={202: {"model": AnalysisJobV1}},
)
async def get(
    id: GameId,
    ply: Annotated[int, Path(ge=1, le=9007199254740991)],
    request: Request,
    record: Annotated[SessionRecord, Depends(current_session)],
):
    status, payload = await service(request).get(UUID(id), record.user.id, ply)
    return JSONResponse(payload, status_code=status)
