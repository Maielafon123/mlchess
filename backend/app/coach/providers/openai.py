"""OpenAI-compatible provider with injected transport.

The transport is deliberately injected so backend integration can own secrets,
HTTP client lifecycle and tracing. This module never reads an API key in JS or
constructs prompts from untrusted client text.
"""

from collections.abc import Callable
from typing import Any

from .base import (
    PROMPT_VERSION,
    CoachProviderError,
    CoachRequest,
    CoachSettings,
    build_grounded_prompt,
)


class OpenAICoachProvider:
    def __init__(
        self,
        *,
        model_id: str,
        settings: CoachSettings,
        generate: Callable[[str, str, float], dict[str, Any]] | None = None,
    ):
        settings.validate_model(model_id)
        self.model_id = model_id
        self.settings = settings
        self._generate = generate

    def explain(self, request: CoachRequest) -> dict[str, Any]:
        if self._generate is None:
            raise CoachProviderError(
                "PROVIDER_UNAVAILABLE",
                "OpenAI transport is not configured",
                retryable=True,
            )
        prompt = build_grounded_prompt(request)
        try:
            result = self._generate(
                self.model_id, prompt, self.settings.timeout_seconds
            )
        except TimeoutError as exc:
            raise CoachProviderError(
                "PROVIDER_TIMEOUT", "Coach provider timed out", retryable=True
            ) from exc
        except Exception as exc:
            raise CoachProviderError(
                "PROVIDER_ERROR", "Coach provider failed", retryable=True
            ) from exc
        result.setdefault("model_id", self.model_id)
        result.setdefault("prompt_version", PROMPT_VERSION)
        result.setdefault("fallback_used", False)
        return result
