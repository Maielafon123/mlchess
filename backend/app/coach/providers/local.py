from collections.abc import Callable
from typing import Any

from .base import PROMPT_VERSION, CoachProviderError, CoachRequest, CoachSettings, build_grounded_prompt


class LocalCoachProvider:
    def __init__(self, *, model_id: str, settings: CoachSettings, generate: Callable[[str, str, float], dict[str, Any]] | None = None):
        settings.validate_model(model_id)
        self.model_id = model_id
        self.settings = settings
        self._generate = generate

    def explain(self, request: CoachRequest) -> dict[str, Any]:
        if self._generate is None:
            raise CoachProviderError("PROVIDER_UNAVAILABLE", "Local coach runtime is not configured", retryable=True)
        try:
            result = self._generate(self.model_id, build_grounded_prompt(request), self.settings.timeout_seconds)
        except TimeoutError as exc:
            raise CoachProviderError("PROVIDER_TIMEOUT", "Local coach runtime timed out", retryable=True) from exc
        except Exception as exc:
            raise CoachProviderError("PROVIDER_ERROR", "Local coach runtime failed", retryable=True) from exc
        result.setdefault("model_id", self.model_id)
        result.setdefault("prompt_version", PROMPT_VERSION)
        result.setdefault("fallback_used", False)
        return result
