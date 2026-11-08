"""Participant-scoped, idempotent analysis acceptance and verified result reads."""

from datetime import timedelta
from uuid import UUID, uuid4

from sqlalchemy import func, select

from backend.app.analysis.service import AnalysisError, reconstruct_position
from backend.app.games.durable import (
    DurableGameService,
    decode_domain,
    fingerprint,
    iso,
)
from backend.app.infra.generated.contracts import AnalysisJobV1, AnalysisResultV1
from backend.app.infra.models import Analysis, OutboxEvent, WorkerJob
from backend.app.infra.problems import PublicProblem, problem_response

# Bump when engine/model, scoring policy or effective limits change.
POLICY = "stockfish-15.1-4-nnue-v1"
POLICY_BINARY_SHA256 = (
    "af67e5f96d92cf6a730f89291ea439ba90ca5bf7921e5d740d79ccfc4584bc92"
)
LEVELS = {
    "quick": {"time_ms": 200, "depth": 12},
    "deep": {"time_ms": 1000, "depth": 18},
}


def require_analysis(game):
    if game.mode not in {"ai", "coach"} and game.status != "finished":
        raise PublicProblem(403)


def position(domain, ply):
    try:
        return reconstruct_position(domain, ply)
    except AnalysisError:
        raise PublicProblem(422) from None


def job_snapshot(analysis, job, event):
    status = "failed" if job.status == "stale" else job.status
    error = None
    if status == "failed":
        import json

        error = json.loads(problem_response(503, str(job.id)).body)
    return AnalysisJobV1.model_validate(
        {
            "schema_version": 1,
            "id": str(job.id),
            "game_id": str(analysis.game_id),
            "revision": analysis.revision,
            "ply": analysis.ply,
            "position_key": event.payload["position_key"],
            "status": status,
            "analysis_id": str(analysis.id) if status == "done" else None,
            "error": error,
            "created_at": iso(job.created_at),
            "updated_at": iso(job.finished_at or analysis.updated_at),
        }
    ).model_dump(mode="json")


class DurableAnalysisService:
    def __init__(self, factory):
        self.factory = factory

    @staticmethod
    async def budget(session, actor_id, now):
        if session.bind.dialect.name == "postgresql":
            await session.execute(select(func.pg_advisory_xact_lock(750120261109)))
        recent = await session.scalar(
            select(func.count())
            .select_from(OutboxEvent)
            .where(
                OutboxEvent.event_type.in_(["analysis.requested", "analysis.retried"]),
                OutboxEvent.created_at >= now - timedelta(hours=1),
                OutboxEvent.payload["actor_id"].as_string() == str(actor_id),
            )
        )
        pending = await session.scalar(
            select(func.count())
            .select_from(WorkerJob)
            .where(
                WorkerJob.queue == "analysis",
                WorkerJob.status.in_(["pending", "running"]),
            )
        )
        if recent >= 40 or pending >= 256:
            raise PublicProblem(429)

    async def submit(self, game_id: UUID, actor_id: UUID, key: UUID, payload: dict):
        digest = fingerprint("analysis", {"game_id": str(game_id), **payload})
        async with self.factory() as session, session.begin():
            await DurableGameService.lock_actor(session, actor_id)
            game, state, _ = await DurableGameService.load(
                session, game_id, actor_id, lock=True
            )
            require_analysis(game)
            domain = decode_domain(state.domain)
            slice_ = position(domain, payload["ply"])
            prior = await DurableGameService.receipt(
                session, actor_id, key, digest, "analysis"
            )
            if prior is not None:
                if (
                    prior["revision"] != game.revision
                    or prior["position_key"] != slice_.position_key
                ):
                    raise PublicProblem(409)
                return prior
            cache_key = fingerprint(
                POLICY,
                {"position": slice_.position_key, "level": payload["analysis_level"]},
            )
            analysis = await session.scalar(
                select(Analysis).where(
                    Analysis.game_id == game_id,
                    Analysis.revision == game.revision,
                    Analysis.ply == payload["ply"],
                    Analysis.cache_key == cache_key,
                )
            )
            now = await DurableGameService.now(session)
            if analysis is None:
                await self.budget(session, actor_id, now)
                analysis = Analysis(
                    id=uuid4(),
                    game_id=game_id,
                    ply=payload["ply"],
                    revision=game.revision,
                    cache_key=cache_key,
                    status="pending",
                    created_at=now,
                    updated_at=now,
                )
                session.add(analysis)
                event = OutboxEvent(
                    id=analysis.id,
                    aggregate_type="analysis",
                    aggregate_id=analysis.id,
                    event_type="analysis.requested",
                    created_at=now,
                    payload={
                        "actor_id": str(actor_id),
                        "level": payload["analysis_level"],
                        "position_key": slice_.position_key,
                        "policy": POLICY,
                        "initial_fen": domain.initial_fen,
                        "moves": [m.uci for m in domain.moves[: payload["ply"]]],
                    },
                )
                session.add(event)
                await session.flush()
                job = WorkerJob(
                    id=analysis.id,
                    game_id=game_id,
                    queue="analysis",
                    expected_version=game.version,
                    revision=game.revision,
                    status="pending",
                    attempts=0,
                    available_at=now,
                    created_at=now,
                )
                session.add(job)
            else:
                job = await session.get(WorkerJob, analysis.id)
                event = await session.get(OutboxEvent, analysis.id)
                if job is None or event is None:
                    raise PublicProblem(503)
                if job.status in {"failed", "stale"}:
                    # A new explicit command may retry the same still-authorized
                    # position. Old command receipts remain exact and immutable.
                    await self.budget(session, actor_id, now)
                    job.status, job.attempts, job.available_at = "pending", 0, now
                    job.failure_code = job.finished_at = job.lease_token = (
                        job.lease_until
                    ) = job.output = None
                    analysis.status, analysis.updated_at = "pending", now
                    analysis.result = analysis.error_code = None
                    event.payload = {**event.payload, "actor_id": str(actor_id)}
                    session.add(
                        OutboxEvent(
                            aggregate_type="analysis",
                            aggregate_id=analysis.id,
                            event_type="analysis.retried",
                            created_at=now,
                            payload={"actor_id": str(actor_id)},
                        )
                    )
            response = job_snapshot(analysis, job, event)
            DurableGameService.remember(
                session, actor_id, key, digest, game_id, response, "analysis"
            )
            return response

    async def get(self, game_id: UUID, actor_id: UUID, ply: int):
        async with self.factory() as session, session.begin():
            # A game lock gives the read a coherent history/revision with takebacks.
            game, state, _ = await DurableGameService.load(
                session, game_id, actor_id, lock=True
            )
            require_analysis(game)
            slice_ = position(decode_domain(state.domain), ply)
            analysis = await session.scalar(
                select(Analysis)
                .where(
                    Analysis.game_id == game_id,
                    Analysis.revision == game.revision,
                    Analysis.ply == ply,
                )
                .order_by(Analysis.created_at.desc(), Analysis.id.desc())
                .limit(1)
            )
            if analysis is None:
                raise PublicProblem(404)
            job, event = (
                await session.get(WorkerJob, analysis.id),
                await session.get(OutboxEvent, analysis.id),
            )
            if (
                job is None
                or event is None
                or event.payload["position_key"] != slice_.position_key
            ):
                raise PublicProblem(503)
            if job.status == "done":
                result = AnalysisResultV1.model_validate(analysis.result).model_dump(
                    mode="json"
                )
                if (
                    result["revision"] != game.revision
                    or result["position_key"] != slice_.position_key
                    or result["analysis_id"] != str(analysis.id)
                    or result["game_id"] != str(game_id)
                    or result["ply"] != ply
                    or result["before_fen"] != slice_.before.fen()
                    or result["after_fen"] != slice_.after.fen()
                ):
                    raise PublicProblem(503)
                return 200, result
            return 202, job_snapshot(analysis, job, event)
