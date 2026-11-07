"""B-013 coach job service.

The store is intentionally in-memory until A-011 queue/A-016 persistence are
available. Its interface mirrors the durable job contract so integration can
replace storage without changing the route semantics.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable
from uuid import uuid4

from .grounding import AnalysisFacts, validate_explanation
from .providers.base import CoachProvider, CoachProviderError, CoachRequest, PROMPT_VERSION


@dataclass
class CoachJob:
    id: str
    request: CoachRequest
    cache_key: str
    status: str = "pending"
    explanation: dict[str, Any] | None = None
    failure_code: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def payload(self) -> dict[str, Any]:
        return {"job_id": self.id, "status": self.status, "created_at": self.created_at, "explanation": self.explanation, "failure_code": self.failure_code}


class CoachService:
    def __init__(self, *, provider: CoachProvider, quota_hook: Callable[[CoachRequest], None] | None = None):
        self.provider = provider
        self.quota_hook = quota_hook
        self.jobs: dict[str, CoachJob] = {}
        self.cache: dict[str, dict[str, Any]] = {}

    def cache_key(self, request: CoachRequest) -> str:
        model = getattr(self.provider, "model_id", "unknown")
        return ":".join((request.analysis_id, model, PROMPT_VERSION, request.language, request.level))

    def submit(self, request: CoachRequest) -> CoachJob:
        key = self.cache_key(request)
        for job in self.jobs.values():
            if job.cache_key == key and job.status in {"pending", "ready"}:
                return job
        if self.quota_hook:
            self.quota_hook(request)
        job = CoachJob(id=str(uuid4()), request=request, cache_key=key)
        self.jobs[job.id] = job
        return job

    def run(self, job_id: str, facts: AnalysisFacts) -> CoachJob:
        job = self.jobs[job_id]
        if job.status == "ready":
            return job
        if (facts.game_id, facts.analysis_id) != (job.request.game_id, job.request.analysis_id) or facts.revision != job.request.revision or facts.ply != job.request.ply:
            result = validate_explanation({}, job.request, facts)
            job.explanation, job.failure_code, job.status = result.explanation, "STALE_REVISION", "ready"
            return job
        try:
            raw = self.provider.explain(job.request)
        except CoachProviderError as error:
            raw = None
            job.failure_code = error.code
        result = validate_explanation(raw, job.request, facts)
        job.explanation = result.explanation
        job.failure_code = job.failure_code or result.failure_code
        job.status = "ready"
        self.cache[job.cache_key] = job.explanation
        return job

    def get(self, job_id: str) -> CoachJob | None:
        return self.jobs.get(job_id)
