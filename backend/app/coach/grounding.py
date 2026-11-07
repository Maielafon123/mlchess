"""Strict grounding gate for coach explanations (B-012).

The validator treats provider output as untrusted data. Any mismatch with the
verified analysis facts is converted into a deterministic fallback rather than
being shown as a chess claim.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json

from jsonschema import Draft202012Validator, FormatChecker

from .providers.base import PROMPT_VERSION, CoachRequest


_SCHEMA_PATH = (
    Path(__file__).resolve().parents[3]
    / "contracts"
    / "coach"
    / "coach-explanation-v1.schema.json"
)
_SCHEMA = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
_VALIDATOR = Draft202012Validator(_SCHEMA, format_checker=FormatChecker())
_INJECTION_MARKERS = (
    "ignore previous",
    "ignore all instructions",
    "system message",
    "developer message",
    "<|system|>",
)


@dataclass(frozen=True)
class AnalysisFacts:
    game_id: str
    analysis_id: str
    revision: int
    ply: int
    verified_uci: frozenset[str] = frozenset()
    verified_highlights: frozenset[str] = frozenset()
    claim_refs: frozenset[str] = frozenset()
    has_mate: bool = False


@dataclass(frozen=True)
class GroundingResult:
    explanation: dict[str, Any]
    accepted: bool
    failure_code: str | None = None


def _fallback(request: CoachRequest, code: str) -> GroundingResult:
    ru = request.language == "ru"
    return GroundingResult(
        {
            "schema_version": 1,
            "game_id": request.game_id,
            "revision": request.revision,
            "ply": request.ply,
            "analysis_id": request.analysis_id,
            "language": request.language,
            "level": request.level,
            "summary": "Недостаточно проверенных данных для объяснения."
            if ru
            else "There is not enough verified data for an explanation.",
            "why": "Попробуйте запросить объяснение после готовности анализа позиции."
            if ru
            else "Request the explanation again when position analysis is ready.",
            "question": "Что изменилось в позиции после хода?"
            if ru
            else "What changed in the position after the move?",
            "referenced_uci": [],
            "highlight_squares": [],
            "claim_refs": [],
            "template_id": "fallback.insufficient-grounding.v1",
            "confidence": "fallback",
            "model_id": "deterministic-fallback",
            "prompt_version": PROMPT_VERSION,
            "fallback_used": True,
        },
        False,
        code,
    )


def _contains_injection(value: Any) -> bool:
    if isinstance(value, str):
        lowered = value.lower()
        return any(marker in lowered for marker in _INJECTION_MARKERS)
    if isinstance(value, dict):
        return any(_contains_injection(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_injection(item) for item in value)
    return False


def validate_explanation(
    raw: Any, request: CoachRequest, facts: AnalysisFacts
) -> GroundingResult:
    if not isinstance(raw, dict):
        return _fallback(request, "MALFORMED_JSON")
    if _contains_injection(raw):
        return _fallback(request, "PROMPT_INJECTION")
    errors = list(_VALIDATOR.iter_errors(raw))
    if errors:
        return _fallback(request, "SCHEMA_INVALID")
    identity = (raw["game_id"], raw["analysis_id"], raw["revision"], raw["ply"])
    expected = (facts.game_id, facts.analysis_id, facts.revision, facts.ply)
    if identity != expected:
        return _fallback(request, "IDENTITY_MISMATCH")
    if raw["language"] != request.language or raw["level"] != request.level:
        return _fallback(request, "REQUEST_METADATA_MISMATCH")
    if raw["prompt_version"] != PROMPT_VERSION:
        return _fallback(request, "PROMPT_VERSION_MISMATCH")
    if raw["fallback_used"]:
        return _fallback(request, "PROVIDER_FALLBACK_NOT_VERIFIED")
    if not set(raw["referenced_uci"]).issubset(facts.verified_uci):
        return _fallback(request, "UNVERIFIED_MOVE")
    if not set(raw["highlight_squares"]).issubset(facts.verified_highlights):
        return _fallback(request, "UNVERIFIED_HIGHLIGHT")
    if not set(raw["claim_refs"]).issubset(facts.claim_refs):
        return _fallback(request, "UNVERIFIED_CLAIM")
    text = " ".join(str(raw[field]).lower() for field in ("summary", "why", "question"))
    if not facts.has_mate and ("checkmate" in text or "mate" in text or "мат" in text):
        return _fallback(request, "INVENTED_MATE")
    return GroundingResult(raw, True)
