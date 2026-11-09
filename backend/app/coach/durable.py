"""SQL-backed principal-scoped jobs around the B-owned pure coaching domain."""

from datetime import timedelta
from uuid import UUID, uuid4

from sqlalchemy import func, select

from backend.app.coach.analysis_reader import read_verified
from backend.app.coach.providers.base import CoachRequest, PROMPT_VERSION
from backend.app.coach.providers.rules import RulesCoachProvider
from backend.app.games.durable import DurableGameService, fingerprint
from backend.app.infra.generated.contracts import CoachJobV1
from backend.app.infra.models import CoachExplanation, OutboxEvent, WorkerJob
from backend.app.infra.problems import PublicProblem


def domain_request(row):
    return CoachRequest(
        game_id=str(row.game_id),
        analysis_id=str(row.analysis_id),
        revision=row.revision,
        ply=row.ply,
        language=row.language,
        level=row.level,
        student_context_version=row.student_context_version,
    )


def snapshot(row, job):
    payload = {
        "schema_version": 1,
        "job_id": str(row.id),
        "game_id": str(row.game_id),
        "analysis_id": str(row.analysis_id),
        "revision": row.revision,
        "ply": row.ply,
        "status": "pending",
    }
    if job.status == "done" and row.status == "ready" and row.payload_json:
        payload.update(status="ready", explanation=row.payload_json)
    elif job.status in {"failed", "stale"}:
        payload.update(
            status="failed",
            error_code="STALE_REVISION" if job.status == "stale" else "COACH_FAILED",
        )
    return CoachJobV1.model_validate(payload).model_dump(mode="json", exclude_none=True)


class DurableCoachService:
    def __init__(self, factory, *, model_id=RulesCoachProvider.model_id):
        self.factory = factory
        self.model_id = model_id

    async def submit(self, actor_id: UUID, key: UUID, payload: dict):
        request = CoachRequest(
            **{k: v for k, v in payload.items() if k != "schema_version"}
        )
        digest = fingerprint("coach", payload)
        async with self.factory() as session, session.begin():
            await DurableGameService.lock_actor(session, actor_id)
            game, _, _ = await read_verified(session, actor_id, request)
            prior = await DurableGameService.receipt(
                session, actor_id, key, digest, "coach"
            )
            if prior is not None:
                return prior
            context = request.student_context_version or "default"
            row = await session.scalar(
                select(CoachExplanation).where(
                    CoachExplanation.requester_id == actor_id,
                    CoachExplanation.analysis_id == UUID(request.analysis_id),
                    CoachExplanation.model_id == self.model_id,
                    CoachExplanation.prompt_version == PROMPT_VERSION,
                    CoachExplanation.language == request.language,
                    CoachExplanation.level == request.level,
                    CoachExplanation.student_context_version == context,
                )
            )
            now = await DurableGameService.now(session)
            if row is None:
                if session.bind.dialect.name == "postgresql":
                    await session.execute(
                        select(func.pg_advisory_xact_lock(750220261109))
                    )
                recent = await session.scalar(
                    select(func.count())
                    .select_from(CoachExplanation)
                    .where(
                        CoachExplanation.requester_id == actor_id,
                        CoachExplanation.created_at >= now - timedelta(hours=1),
                    )
                )
                pending = await session.scalar(
                    select(func.count())
                    .select_from(WorkerJob)
                    .where(
                        WorkerJob.queue == "coach",
                        WorkerJob.status.in_(["pending", "running"]),
                    )
                )
                if self.model_id.startswith("openai:"):
                    remote_recent = await session.scalar(
                        select(func.count())
                        .select_from(CoachExplanation)
                        .where(
                            CoachExplanation.model_id.startswith("openai:"),
                            CoachExplanation.created_at >= now - timedelta(hours=1),
                        )
                    )
                    if remote_recent >= 120 or recent >= 20:
                        raise PublicProblem(429)
                if recent >= 120 or pending >= 256:
                    raise PublicProblem(429)
                job_id = uuid4()
                session.add(
                    OutboxEvent(
                        id=job_id,
                        aggregate_type="coach",
                        aggregate_id=job_id,
                        event_type="coach.requested",
                        payload={"actor_id": str(actor_id)},
                        created_at=now,
                    )
                )
                await session.flush()
                row = CoachExplanation(
                    id=job_id,
                    requester_id=actor_id,
                    analysis_id=UUID(request.analysis_id),
                    game_id=game.id,
                    revision=request.revision,
                    ply=request.ply,
                    model_id=self.model_id,
                    prompt_version=PROMPT_VERSION,
                    language=request.language,
                    level=request.level,
                    student_context_version=context,
                    status="pending",
                    fallback_used=False,
                    created_at=now,
                )
                session.add(row)
                job = WorkerJob(
                    id=job_id,
                    game_id=game.id,
                    queue="coach",
                    expected_version=game.version,
                    revision=game.revision,
                    status="pending",
                    attempts=0,
                    available_at=now,
                    created_at=now,
                )
                session.add(job)
            else:
                job = await session.get(WorkerJob, row.id)
                if job is None:
                    raise PublicProblem(503)
            response = snapshot(row, job)
            DurableGameService.remember(
                session, actor_id, key, digest, game.id, response, "coach"
            )
            return response

    async def get(self, game_id: UUID, actor_id: UUID, job_id: UUID):
        async with self.factory() as session, session.begin():
            # Coherent game/analysis revision while a concurrent undo waits.
            await DurableGameService.load(session, game_id, actor_id, lock=True)
            row = await session.get(CoachExplanation, job_id)
            if row is None or row.game_id != game_id:
                raise PublicProblem(404)
            if row.requester_id != actor_id:
                raise PublicProblem(403)
            await read_verified(session, actor_id, domain_request(row))
            job = await session.get(WorkerJob, job_id)
            if job is None or job.queue != "coach":
                raise PublicProblem(503)
            return snapshot(row, job)
