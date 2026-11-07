import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker, RefResolver


ROOT = Path(__file__).resolve().parents[3]
CONTRACTS = ROOT / "contracts" / "coach"
FIXTURES = CONTRACTS / "fixtures"


def load_schema(name: str) -> dict:
    return json.loads((CONTRACTS / name).read_text(encoding="utf-8"))


def validator_for(name: str) -> Draft202012Validator:
    schema = load_schema(name)
    resolver = RefResolver((CONTRACTS / name).as_uri(), schema)
    return Draft202012Validator(schema, resolver=resolver, format_checker=FormatChecker())


@pytest.mark.parametrize("fixture_name", ["valid.json", "mate.json", "no-motif.json", "rejected-fallback.json", "stale-revision.json"])
def test_explanation_fixtures_match_v1(fixture_name: str) -> None:
    payload = json.loads((FIXTURES / fixture_name).read_text(encoding="utf-8"))
    errors = sorted(validator_for("coach-explanation-v1.schema.json").iter_errors(payload), key=lambda error: error.path)
    assert errors == [], "\n".join(error.message for error in errors)


def test_request_rejects_idempotency_key_in_body() -> None:
    payload = {
        "schema_version": 1,
        "game_id": "2de40e7e-5241-423e-8fce-2ef1645595dc",
        "analysis_id": "0f650483-7b3d-40f1-8958-5c236483c8b7",
        "revision": 0,
        "ply": 1,
        "language": "ru",
        "level": "short",
        "idempotency_key": "should-be-a-header",
    }
    errors = list(validator_for("coach-request-v1.schema.json").iter_errors(payload))
    assert any("Additional properties" in error.message for error in errors)


def test_job_requires_explanation_when_ready() -> None:
    schema = load_schema("coach-job-v1.schema.json")
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    payload = {
        "schema_version": 1,
        "job_id": "2de40e7e-5241-423e-8fce-2ef1645595dc",
        "status": "ready",
        "game_id": "2de40e7e-5241-423e-8fce-2ef1645595dc",
        "analysis_id": "0f650483-7b3d-40f1-8958-5c236483c8b7",
        "revision": 0,
        "ply": 1,
    }
    errors = list(validator.iter_errors(payload))
    assert any("explanation" in error.message for error in errors)
