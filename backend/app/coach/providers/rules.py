"""Truthful deterministic coaching from verified engine facts, without an LLM."""

from .base import PROMPT_VERSION, CoachRequest


class RulesCoachProvider:
    model_id = "verified-rules-v1"

    def explain(self, request: CoachRequest):
        data, ru = request.analysis, request.language == "ru"
        played, best = data["played_move"], data["best_move"]
        show_best = request.level in {"candidates", "solution", "detailed"}
        summary = (
            f"Разберём сыгранный ход {played}."
            if ru
            else f"Review the played move {played}."
        )
        why = (
            "Сравните позицию до хода и после него: какие фигуры изменили положение?"
            if ru
            else "Compare the positions before and after the move: which pieces changed squares?"
        )
        refs, claims = [played], []
        if data["facts"]["checks"]:
            why = (
                "После этого хода король соперника под шахом."
                if ru
                else "After this move, the opposing king is in check."
            )
            claims = [
                c["fact_id"]
                for c in data["facts"]["verified_claims"]
                if c["kind"] == "check"
            ]
        elif data["facts"]["captures"]:
            capture = next(
                c for c in data["facts"]["verified_claims"] if c["kind"] == "capture"
            )
            square = capture["evidence"]["square"]
            why = (
                f"Этим ходом взята фигура на поле {square}."
                if ru
                else f"This move captured a piece on {square}."
            )
            claims = [capture["fact_id"]]
        if show_best:
            why += (
                f" До сыгранного хода движок предпочитал {best}."
                if ru
                else f" Before the played move, the engine preferred {best}."
            )
            refs = list(dict.fromkeys([played, best]))
            claims.append("analysis.best_move")
        question = (
            "Что изменилось в положении фигур после вашего хода?"
            if ru
            else "What changed in the placement of the pieces after your move?"
        )
        if request.level in {"direction", "idea"}:
            question = (
                "Какие взятия и шахи стоит проверить в этой позиции?"
                if ru
                else "Which captures and checks are worth examining in this position?"
            )
        return {
            "schema_version": 1,
            "game_id": request.game_id,
            "analysis_id": request.analysis_id,
            "revision": request.revision,
            "ply": request.ply,
            "language": request.language,
            "level": request.level,
            "summary": summary,
            "why": why,
            "question": question,
            "referenced_uci": refs,
            "highlight_squares": sorted(
                {square for move in refs for square in (move[:2], move[2:4])}
            ),
            "claim_refs": claims,
            "template_id": "verified-rules." + request.level + ".v1",
            "confidence": "grounded",
            "model_id": self.model_id,
            "prompt_version": PROMPT_VERSION,
            "fallback_used": False,
        }
