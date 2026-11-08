"""Session-scoped learning adapters; all grading and progress are server owned."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Path, Query, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, model_validator

from backend.app.auth.router import current_session
from backend.app.auth.service import SessionRecord
from backend.app.games.router import key, writer
from backend.app.infra.generated import contracts as dto
from backend.app.infra.problems import PublicProblem

Slug = Annotated[str, Path(min_length=1, max_length=80, pattern=r"^[a-z0-9-]+$")]
Language = Literal["ru", "en"]
Reader = Annotated[SessionRecord, Depends(current_session)]
Writer = Annotated[SessionRecord, Depends(writer)]
CommandKey = Annotated[str, Header(max_length=36)]


class StrictCommand(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    @model_validator(mode="before")
    @classmethod
    def strict_scalars(cls, data):
        if isinstance(data, dict):
            for name in (
                "schema_version",
                "learning_epoch",
                "session_number",
                "expected_ply",
            ):
                if name in cls.model_fields and type(data.get(name)) is not int:
                    raise ValueError("JSON integers are required")
            if "confirm" in cls.model_fields and data.get("confirm") is not True:
                raise ValueError("Explicit confirmation is required")
        return data


class StatusRequest(StrictCommand, dto.LessonStatusRequestV1):
    pass


class AttemptRequest(StrictCommand, dto.PuzzleAttemptRequestV1):
    pass


class SessionRequest(StrictCommand, dto.PuzzleSessionRequestV1):
    pass


class ResetRequest(StrictCommand, dto.LearningResetV1):
    pass


def service(request):
    value = request.app.state.learning_service
    if value is None:
        raise PublicProblem(503)
    return value


def validated(model, payload):
    # Keep required nulls (due_at, next_cursor), but omit solution before completion.
    model.model_validate(payload)
    return JSONResponse(payload)


def create_durable_router() -> APIRouter:
    scoped = APIRouter(prefix="/api/v1/learning", tags=["learning"])

    @scoped.get(
        "/context",
        response_model=dto.LearningContextV1,
        operation_id="getLearningContext",
    )
    async def context(request: Request, record: Reader):
        return await service(request).read("context", record.user.id)

    @scoped.get("/lessons", response_model=dto.LessonListV1, operation_id="listLessons")
    async def lessons(
        request: Request,
        record: Reader,
        language: Language = "ru",
        page: Annotated[int, Query(ge=1, le=100000)] = 1,
        page_size: Annotated[int, Query(ge=1, le=24)] = 6,
    ):
        return await service(request).read(
            "lessons", record.user.id, language=language, page=page, page_size=page_size
        )

    @scoped.get("/lessons/{id}", response_model=dto.LessonV1, operation_id="getLesson")
    async def lesson(
        id: Slug, request: Request, record: Reader, language: Language = "ru"
    ):
        return await service(request).read(
            "lesson", record.user.id, target=id, language=language
        )

    @scoped.post(
        "/lessons/{id}/status",
        response_model=dto.LessonV1,
        operation_id="updateLessonStatus",
    )
    async def status(
        id: Slug,
        payload: StatusRequest,
        request: Request,
        record: Writer,
        idempotency_key: CommandKey,
        language: Language = "ru",
    ):
        return await service(request).command(
            "lesson-status",
            record.user.id,
            key(request, idempotency_key),
            payload.model_dump(mode="json"),
            target=id,
            language=language,
        )

    @scoped.get("/puzzles", response_model=dto.PuzzleListV1, operation_id="listPuzzles")
    async def puzzles(request: Request, record: Reader):
        return await service(request).read("puzzles", record.user.id)

    @scoped.get("/puzzles/{id}", response_model=dto.PuzzleV1, operation_id="getPuzzle")
    async def puzzle(id: Slug, request: Request, record: Reader):
        return await service(request).read("puzzle", record.user.id, target=id)

    @scoped.get(
        "/puzzles/{id}/state",
        response_model=dto.PuzzleStateV1,
        operation_id="getPuzzleState",
    )
    async def state(
        id: Slug, request: Request, record: Reader, language: Language = "ru"
    ):
        return validated(
            dto.PuzzleStateV1,
            await service(request).read(
                "state", record.user.id, target=id, language=language
            ),
        )

    @scoped.post(
        "/puzzles/{id}/attempts",
        response_model=dto.PuzzleAttemptV1,
        operation_id="submitPuzzleAttempt",
    )
    async def attempt(
        id: Slug,
        payload: AttemptRequest,
        request: Request,
        record: Writer,
        idempotency_key: CommandKey,
    ):
        return await service(request).command(
            "attempt",
            record.user.id,
            key(request, idempotency_key),
            payload.model_dump(mode="json"),
            target=id,
        )

    @scoped.post(
        "/puzzles/{id}/hints",
        response_model=dto.PuzzleHintV1,
        operation_id="requestPuzzleHint",
    )
    async def hint(
        id: Slug,
        payload: SessionRequest,
        request: Request,
        record: Writer,
        idempotency_key: CommandKey,
        language: Language = "ru",
    ):
        return await service(request).command(
            "hint",
            record.user.id,
            key(request, idempotency_key),
            payload.model_dump(mode="json"),
            target=id,
            language=language,
        )

    @scoped.post(
        "/puzzles/{id}/restart",
        response_model=dto.PuzzleStateV1,
        operation_id="restartPuzzle",
    )
    async def restart(
        id: Slug,
        payload: SessionRequest,
        request: Request,
        record: Writer,
        idempotency_key: CommandKey,
        language: Language = "ru",
    ):
        return validated(
            dto.PuzzleStateV1,
            await service(request).command(
                "restart",
                record.user.id,
                key(request, idempotency_key),
                payload.model_dump(mode="json"),
                target=id,
                language=language,
            ),
        )

    def own_student(record, student_id):
        if student_id is not None and student_id != record.user.id:
            raise PublicProblem(403)

    @scoped.get(
        "/progress",
        response_model=dto.StudentProgressV1,
        operation_id="getStudentProgress",
    )
    async def progress(
        request: Request, record: Reader, student_id: UUID | None = None
    ):
        own_student(record, student_id)
        return await service(request).read("progress", record.user.id)

    @scoped.get(
        "/review-queue",
        response_model=dto.StudentProgressV1,
        operation_id="getReviewQueue",
    )
    async def review(request: Request, record: Reader, student_id: UUID | None = None):
        own_student(record, student_id)
        return await service(request).read("review", record.user.id)

    @scoped.get(
        "/export",
        response_model=dto.LearningExportV1,
        operation_id="exportLearningData",
    )
    async def export(
        request: Request,
        record: Reader,
        cursor: Annotated[str | None, Query(min_length=1, max_length=300)] = None,
    ):
        return validated(
            dto.LearningExportV1,
            await service(request).read("export", record.user.id, cursor=cursor),
        )

    @scoped.delete("/data", status_code=204, operation_id="deleteLearningData")
    async def reset(
        payload: ResetRequest,
        request: Request,
        record: Writer,
        idempotency_key: CommandKey,
    ):
        await service(request).command(
            "reset",
            record.user.id,
            key(request, idempotency_key),
            payload.model_dump(mode="json"),
        )
        return Response(status_code=204)

    return scoped
