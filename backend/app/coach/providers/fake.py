from typing import Any

from .base import PROMPT_VERSION, CoachRequest, CoachSettings


class FakeCoachProvider:
    model_id = "fake-coach-v1"

    def __init__(self, settings: CoachSettings | None = None):
        self.settings = settings or CoachSettings()
        self.settings.validate_model(self.model_id)

    def explain(self, request: CoachRequest) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "game_id": request.game_id,
            "revision": request.revision,
            "ply": request.ply,
            "analysis_id": request.analysis_id,
            "language": request.language,
            "level": request.level,
            "summary": "Сначала проверьте угрозу соперника." if request.language == "ru" else "Check the opponent's threat first.",
            "why": "Это объяснение создано fake-провайдером для детерминированного теста контракта.",
            "question": "Какую угрозу вы видите после этого хода?",
            "referenced_uci": list(request.analysis.get("referenced_uci", []))[:8],
            "highlight_squares": list(request.analysis.get("highlight_squares", []))[:16],
            "claim_refs": ["analysis.best_move"],
            "template_id": "fake.threat-check.v1",
            "confidence": "grounded",
            "model_id": self.model_id,
            "prompt_version": PROMPT_VERSION,
            "fallback_used": False,
        }
