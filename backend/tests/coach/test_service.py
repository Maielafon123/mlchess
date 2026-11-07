import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.coach.grounding import AnalysisFacts
from backend.app.coach.providers import CoachSettings, FakeCoachProvider
from backend.app.coach.router import create_router
from backend.app.coach.service import CoachService
from backend.app.coach.providers.base import CoachRequest


ROOT = Path(__file__).resolve().parents[3]
FIXTURE = json.loads((ROOT / "contracts/coach/fixtures/valid.json").read_text(encoding="utf-8"))


def request() -> CoachRequest:
    return CoachRequest(game_id=FIXTURE["game_id"], analysis_id=FIXTURE["analysis_id"], revision=FIXTURE["revision"], ply=FIXTURE["ply"], language="en", level="detailed")


def facts(revision: int = 3) -> AnalysisFacts:
    return AnalysisFacts(FIXTURE["game_id"], FIXTURE["analysis_id"], revision, FIXTURE["ply"], frozenset(), frozenset(), frozenset(), False)


def test_submit_is_deduplicated_and_run_returns_ready():
    service = CoachService(provider=FakeCoachProvider(CoachSettings()))
    first = service.submit(request())
    duplicate = service.submit(request())
    assert first.id == duplicate.id
    done = service.run(first.id, facts())
    assert done.status == "ready"
    assert done.explanation["fallback_used"] is True


def test_stale_revision_never_uses_provider_explanation():
    service = CoachService(provider=FakeCoachProvider(CoachSettings()))
    job = service.submit(request())
    done = service.run(job.id, facts(revision=99))
    assert done.failure_code == "STALE_REVISION"
    assert done.explanation["fallback_used"] is True


def test_router_exposes_202_then_200_ready():
    service = CoachService(provider=FakeCoachProvider(CoachSettings()))
    app = FastAPI()
    app.include_router(create_router(service, facts_loader=lambda _request: facts()))
    client = TestClient(app)
    response = client.post("/api/v1/coach-requests", json={"schema_version": 1, "game_id": FIXTURE["game_id"], "analysis_id": FIXTURE["analysis_id"], "revision": 3, "ply": FIXTURE["ply"], "language": "en", "level": "detailed"})
    assert response.status_code == 202
    job_id = response.json()["job_id"]
    ready = client.get(f"/api/v1/coach-requests/{job_id}")
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"


def test_quota_hook_is_normalized_to_429():
    def reject(_request):
        raise RuntimeError("quota")

    service = CoachService(provider=FakeCoachProvider(), quota_hook=reject)
    app = FastAPI()
    app.include_router(create_router(service))
    client = TestClient(app)
    response = client.post("/api/v1/coach-requests", json={"schema_version": 1, "game_id": FIXTURE["game_id"], "analysis_id": FIXTURE["analysis_id"], "revision": 3, "ply": FIXTURE["ply"], "language": "en", "level": "detailed"})
    assert response.status_code == 429
