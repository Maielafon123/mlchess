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


def create_router(service: CoachService, facts_loader: Callable[[CoachRequest], AnalysisFacts | None] | None = None) -> APIRouter:
    """Create route handlers for A-owned composition.

    A-015 should mount this router and provide the authenticated AnalysisReader
    as ``facts_loader``. Until then, the exported ``router`` stays empty.
    """
    scoped = APIRouter(prefix="/api/v1", tags=["coach"])

    @scoped.post("/coach-requests", status_code=status.HTTP_202_ACCEPTED)
    def submit_coach_request(body: CoachRequestBody, response: Response):
        request = CoachRequest(**body.model_dump(exclude={"schema_version"}))
        try:
            job = service.submit(request)
        except Exception as error:
            raise HTTPException(status_code=429, detail="Coach quota rejected") from error
        response.headers["Location"] = f"/api/v1/coach-requests/{job.id}"
        return job.payload()

    @scoped.get("/coach-requests/{job_id}")
    def get_coach_request(job_id: str):
        job = service.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Coach job not found")
        if job.status == "pending" and facts_loader is not None:
            facts = facts_loader(job.request)
            if facts is not None:
                service.run(job.id, facts)
        return job.payload()

    return scoped
