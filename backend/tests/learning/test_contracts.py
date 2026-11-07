import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[3]


def validate(name: str, payload: dict) -> None:
    schema = json.loads(
        (ROOT / "contracts/learning" / name).read_text(encoding="utf-8")
    )
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(payload)


def test_learning_contracts_validate_bounded_payloads():
    validate(
        "lesson-v1.schema.json",
        {
            "schema_version": 1,
            "id": "opening-center",
            "title": "Center",
            "summary": "Use the center",
            "body": "Develop pieces",
            "language": "en",
            "status": "not-started",
            "source_name": "MLChess",
            "source_url": "https://mlchess.dev/lessons/opening-center",
            "license": "CC BY 4.0",
            "tags": ["opening"],
        },
    )
    validate(
        "puzzle-v1.schema.json",
        {
            "schema_version": 1,
            "id": "back-rank",
            "fen": "6k1/5ppp/8/8/8/8/5PPP/3R2K1 w - - 0 1",
            "difficulty": 1,
            "tags": ["mate"],
            "source_name": "MLChess",
            "source_url": "https://mlchess.dev/puzzles/back-rank",
            "license": "CC BY 4.0",
        },
    )
    validate(
        "puzzle-attempt-v1.schema.json",
        {
            "schema_version": 1,
            "attempt_id": "attempt-1",
            "result": "correct",
            "completed": True,
            "next_ply": 1,
        },
    )
    validate(
        "student-progress-v1.schema.json",
        {"schema_version": 1, "student_id": "student-1", "skills": []},
    )


def test_learning_contracts_reject_untrusted_http_source():
    schema = json.loads(
        (ROOT / "contracts/learning/lesson-v1.schema.json").read_text(encoding="utf-8")
    )
    payload = {
        "schema_version": 1,
        "id": "x",
        "title": "x",
        "summary": "x",
        "body": "x",
        "language": "en",
        "status": "not-started",
        "source_name": "x",
        "source_url": "javascript:alert(1)",
        "license": "x",
        "tags": [],
    }
    assert list(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(
            payload
        )
    )
