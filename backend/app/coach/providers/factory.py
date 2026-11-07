from collections.abc import Callable
from typing import Any

from .base import CoachProvider, CoachProviderError, CoachSettings
from .fake import FakeCoachProvider
from .local import LocalCoachProvider
from .openai import OpenAICoachProvider


def build_provider(
    settings: CoachSettings,
    *,
    model_id: str | None = None,
    generate: Callable[[str, str, float], dict[str, Any]] | None = None,
) -> CoachProvider:
    selected_model = model_id or settings.default_model
    if settings.provider == "fake":
        return FakeCoachProvider(settings)
    if settings.provider == "openai":
        return OpenAICoachProvider(
            model_id=selected_model, settings=settings, generate=generate
        )
    if settings.provider == "local":
        return LocalCoachProvider(
            model_id=selected_model, settings=settings, generate=generate
        )
    raise CoachProviderError(
        "PROVIDER_NOT_SUPPORTED", f"Unknown coach provider '{settings.provider}'"
    )
