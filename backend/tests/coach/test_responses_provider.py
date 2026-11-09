"""The optional provider can choose verified teaching options without private inputs."""

import json
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.app.coach.execution import execute
from backend.app.coach.grounding import AnalysisFacts, validate_explanation
from backend.app.coach.providers.base import CoachProviderError, CoachRequest
from backend.app.coach.providers.responses import ENDPOINT, ResponsesCoachProvider
from backend.app.coach.service import CoachJob
from backend.app.infra.settings import Settings
from backend.app.main import create_app


def position(level="idea"):
    request = CoachRequest(
        game_id=str(uuid4()),
        analysis_id=str(uuid4()),
        revision=0,
        ply=1,
        language="ru",
        level=level,
        student_context_version="private-fixture",
        analysis={
            "played_move": "e2e4",
            "best_move": "d2d4",
            "quality": "good",
            "facts": {"checks": False, "captures": False, "verified_claims": []},
        },
    )
    facts = AnalysisFacts(
        request.game_id,
        request.analysis_id,
        request.revision,
        request.ply,
        frozenset({"e2e4", "d2d4"}),
        frozenset({"e2", "e4", "d2", "d4"}),
        frozenset({"analysis.best_move"}),
    )
    return request, facts


def upstream(response_type, *, emphasis="compare"):
    def respond(request):
        assert str(request.url) == ENDPOINT and request.method == "POST"
        assert request.headers["authorization"] == "Bearer fixture-key"
        payload = json.loads(request.content)
        assert payload["store"] is False
        assert payload["max_output_tokens"] == 300
        assert payload["text"]["format"]["strict"] is True
        assert set(json.loads(payload["input"])) == {
            "level",
            "quality",
            "check",
            "capture",
        }
        assert b"private-fixture" not in request.content
        assert b"e2e4" not in request.content
        assert b"d2d4" not in request.content
        if response_type == "redirect":
            return httpx.Response(
                307, headers={"location": "https://invalid.example.test"}
            )
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [
                            {
                                "type": response_type,
                                "text": json.dumps(
                                    {"emphasis": emphasis, "question": "reply"}
                                ),
                            },
                        ],
                    }
                ],
            },
        )

    return httpx.MockTransport(respond)


@pytest.mark.parametrize(
    "level,emphasis", [("idea", "compare"), ("detailed", "engine_preference")]
)
def test_choice_is_rendered_and_validated_locally(level, emphasis):
    request, facts = position(level)
    provider = ResponsesCoachProvider(
        "fixture-model", "fixture-key", upstream("output_text", emphasis=emphasis)
    )
    explanation = provider.explain(request)
    assert validate_explanation(explanation, request, facts).accepted
    assert explanation["model_id"] == "openai:fixture-model"
    assert ("d2d4" in explanation["referenced_uci"]) == (level == "detailed")
    assert ("analysis.best_move" in explanation["claim_refs"]) == (level == "detailed")


@pytest.mark.parametrize(
    "kind,emphasis",
    [("refusal", "compare"), ("output_text", "capture"), ("redirect", "compare")],
)
def test_provider_rejects_refusal_redirect_and_unverified_choices(kind, emphasis):
    request, _ = position()
    with pytest.raises(CoachProviderError, match="valid choice"):
        ResponsesCoachProvider(
            "fixture-model", "fixture-key", upstream(kind, emphasis=emphasis)
        ).explain(request)


def test_cloud_process_failure_uses_verified_local_rules(monkeypatch):
    request, facts = position()
    job = CoachJob(id=str(uuid4()), request=request, cache_key="fixture")
    provider = ResponsesCoachProvider("fixture-model", "fixture-key")

    def timeout(argv, *, input, env, **kwargs):
        assert "fixture-key" not in " ".join(argv)
        assert "fixture-key" not in env.values()
        assert json.loads(input)["provider"]["model"] == "fixture-model"
        raise TimeoutError

    monkeypatch.setattr("backend.app.coach.execution.subprocess.run", timeout)
    explanation, code = execute(provider, job, facts)
    assert code == "PROVIDER_UNAVAILABLE"
    assert explanation["model_id"] == "verified-rules-v1"
    assert validate_explanation(explanation, request, facts).accepted


@pytest.mark.parametrize("model", ["", "fixture-model"])
def test_provider_disclosure_has_no_model_or_credential(model):
    settings = Settings(
        environment="test",
        public_origin="http://testserver",
        coach_openai_model=model,
        coach_openai_api_key="fixture-only",
    )
    with TestClient(create_app(settings)) as client:
        reply = client.get("/api/v1/coach/provider")
    assert reply.status_code == 200
    assert reply.json() == {"schema_version": 1, "external": bool(model)}
