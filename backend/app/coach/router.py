"""Coach router boundary.

The A-owned application composition will mount this router in an integration PR.
No endpoints are registered until the A-owned AnalysisReader and auth/mode guards
are available, so this module deliberately contains only the router object.
"""

from fastapi import APIRouter
from fastapi import HTTPException, Response, status
from pydantic import BaseModel, Field
from collections.abc import Callable
from typing import Literal

from .grounding import AnalysisFacts
from .providers.base import CoachRequest
from .service import CoachService

router = APIRouter(prefix="/api/v1", tags=["coach"])


class CoachRequestBody(BaseModel):
    schema_version: Literal[1] = 1
    game_id: str
    analysis_id: str
    revision: int = Field(ge=0)
    ply: int = Field(ge=1)
    language: str
    level: str
    student_context_version: str | None = None


def create_router(
    service: CoachService,
    facts_loader: Callable[[CoachRequest], AnalysisFacts | None] | None = None,
    *,
    access_guard: Callable[[CoachRequest], bool] | None = None,
    enqueue: Callable[[str], None] | None = None,
) -> APIRouter:
    """Create route handlers for A-owned composition.

    A-015 should mount this router and provide the authenticated AnalysisReader
    as ``facts_loader``. Until then, the exported ``router`` stays empty.
    """
    scoped = APIRouter(prefix="/api/v1", tags=["coach"])

    @scoped.post("/coach-requests", status_code=status.HTTP_202_ACCEPTED)
    def submit_coach_request(body: CoachRequestBody, response: Response):
        request = CoachRequest(**body.model_dump(exclude={"schema_version"}))
        if access_guard is None or not access_guard(request):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Coach request is not allowed for this game",
            )
        try:
            job = service.submit(request)
        except Exception as error:
            raise HTTPException(
                status_code=429, detail="Coach quota rejected"
            ) from error
        response.headers["Location"] = f"/api/v1/coach-requests/{job.id}"
        if enqueue is not None:
            enqueue(job.id)
        return job.payload()

    @scoped.post(
        "/games/{game_id}/coach-requests", status_code=status.HTTP_202_ACCEPTED
    )
    def submit_game_coach_request(
        game_id: str, body: CoachRequestBody, response: Response
    ):
        if body.game_id != game_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Game identity does not match request",
            )
        return submit_coach_request(body, response)

    @scoped.get("/coach-requests/{job_id}")
    def get_coach_request(job_id: str):
        job = service.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Coach job not found")
        if access_guard is None or not access_guard(job.request):
            raise HTTPException(status_code=403, detail="Coach job is not permitted")
        return job.payload()

    @scoped.get("/games/{game_id}/coach-requests/{job_id}")
    def get_game_coach_request(game_id: str, job_id: str):
        job = service.get(job_id)
        if job is None or job.request.game_id != game_id:
            raise HTTPException(status_code=404, detail="Coach job not found")
        if access_guard is None or not access_guard(job.request):
            raise HTTPException(status_code=403, detail="Coach job is not permitted")
        return job.payload()

    return scoped


def create_durable_router() -> APIRouter:
    """Guarded async SQL composition. The legacy in-memory factory is not mounted."""
    from typing import Annotated
    from uuid import UUID

    from fastapi import Depends, Header, Request
    from pydantic import ConfigDict, model_validator, field_validator
    from backend.app.auth.dependencies import GameId, current_session, key, writer
    from backend.app.auth.service import SessionRecord
    from backend.app.infra.generated.contracts import CoachRequestV1, CoachJobV1
    from backend.app.infra.problems import PublicProblem

    class DurableRequest(CoachRequestV1):
        model_config = ConfigDict(extra="forbid", strict=True)

        @model_validator(mode="before")
        @classmethod
        def strict_numbers(cls, data):
            if isinstance(data, dict):
                for name in ("schema_version", "revision", "ply"):
                    if type(data.get(name)) is not int or data[name] > 9007199254740991:
                        raise ValueError("JSON integers are required")
                if data.get("student_context_version", "default") is None:
                    raise ValueError("Context version must be omitted or a string")
            return data

        @field_validator("game_id", "analysis_id")
        @classmethod
        def valid_uuid(cls, value):
            if str(UUID(value)) != value.lower():
                raise ValueError("Canonical UUID is required")
            return value

    scoped = APIRouter(prefix="/api/v1/games", tags=["coach"])

    def durable_service(request):
        if request.app.state.coach_service is None:
            raise PublicProblem(503)
        return request.app.state.coach_service

    @scoped.post(
        "/{id}/coach-requests",
        status_code=202,
        response_model=CoachJobV1,
        response_model_exclude_none=True,
        operation_id="requestCoach",
    )
    async def submit(
        id: GameId,
        payload: DurableRequest,
        request: Request,
        record: Annotated[SessionRecord, Depends(writer)],
        idempotency_key: Annotated[str, Header(max_length=36)],
    ):
        if payload.game_id != id:
            raise PublicProblem(409)
        return await durable_service(request).submit(
            record.user.id,
            key(request, idempotency_key),
            payload.model_dump(mode="json", exclude_unset=True),
        )

    @scoped.get(
        "/{id}/coach-requests/{job_id}",
        response_model=CoachJobV1,
        response_model_exclude_none=True,
        operation_id="getCoach",
    )
    async def get(
        id: GameId,
        job_id: UUID,
        request: Request,
        record: Annotated[SessionRecord, Depends(current_session)],
    ):
        return await durable_service(request).get(UUID(id), record.user.id, job_id)

    return scoped
