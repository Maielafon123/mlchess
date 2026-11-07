"""Provider-neutral coach boundary for B-011.

The adapter returns a contract-shaped dictionary. A-002/A-014 integration can
replace this with generated Pydantic models without changing provider policy.
"""

from dataclasses import dataclass, field
from typing import Any, Protocol
import json

PROMPT_VERSION = "coach-v1"


@dataclass(frozen=True)
class CoachRequest:
    game_id: str
    analysis_id: str
    revision: int
    ply: int
    language: str
    level: str
    student_context_version: str | None = None
    analysis: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CoachSettings:
    provider: str = "fake"
    model_allowlist: frozenset[str] = frozenset({"fake-coach-v1"})
    default_model: str = "fake-coach-v1"
    timeout_seconds: float = 8.0

    def validate_model(self, model_id: str) -> None:
        if model_id not in self.model_allowlist:
            raise CoachProviderError("MODEL_NOT_ALLOWED", f"Model '{model_id}' is not allowlisted")


class CoachProviderError(RuntimeError):
    def __init__(self, code: str, detail: str, *, retryable: bool = False):
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.retryable = retryable


class CoachProvider(Protocol):
    model_id: str

    def explain(self, request: CoachRequest) -> dict[str, Any]: ...


def build_grounded_prompt(request: CoachRequest) -> str:
    """Serialize bounded analysis facts; never pass raw PGN or instructions."""
    allowed_analysis = {key: request.analysis[key] for key in ("referenced_uci", "highlight_squares", "claim_refs", "best_move", "quality") if key in request.analysis}
    payload = {"prompt_version": PROMPT_VERSION, "game_id": request.game_id, "analysis_id": request.analysis_id, "revision": request.revision, "ply": request.ply, "language": request.language, "level": request.level, "analysis": allowed_analysis}
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
