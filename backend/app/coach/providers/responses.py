"""Optional OpenAI teaching choices rendered only from verified local facts."""

from dataclasses import dataclass, field
import json
import re

import httpx

from .base import CoachProviderError, CoachRequest
from .rules import RulesCoachProvider

ENDPOINT = "https://api.openai.com/v1/responses"
QUESTIONS = {
    "activity": (
        "Изменилась ли активность фигур после хода?",
        "Did the move change how active the pieces are?",
    ),
    "reply": (
        "Какой ответ соперника вы бы проверили первым?",
        "Which reply would you check first?",
    ),
    "forcing": (
        "Какие шахи и взятия стоит проверить?",
        "Which checks and captures are worth checking?",
    ),
}


@dataclass(frozen=True)
class ResponsesCoachProvider:
    model: str
    api_key: str = field(repr=False)
    transport: httpx.BaseTransport | None = field(default=None, repr=False)

    @property
    def model_id(self):
        return "openai:" + self.model

    def choose(self, facts, available):
        properties = {
            "emphasis": {"type": "string", "enum": available},
            "question": {"type": "string", "enum": list(QUESTIONS)},
        }
        schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": properties,
            "required": list(properties),
        }
        payload = {
            "model": self.model,
            "store": False,
            "max_output_tokens": 300,
            "instructions": (
                "Choose one teaching emphasis and one follow-up question for a chess learner. "
                "Use only the options in the JSON schema and the supplied verified facts. "
                "The application will write the explanation; do not invent facts or moves."
            ),
            "input": json.dumps(facts, ensure_ascii=False, separators=(",", ":")),
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "chess_teaching_choice",
                    "strict": True,
                    "schema": schema,
                }
            },
        }
        try:
            with (
                httpx.Client(
                    transport=self.transport,
                    timeout=httpx.Timeout(5, connect=2),
                    follow_redirects=False,
                    trust_env=False,
                ) as http,
                http.stream(
                    "POST",
                    ENDPOINT,
                    json=payload,
                    headers={
                        "Authorization": "Bearer " + self.api_key,
                        "Accept-Encoding": "identity",
                    },
                ) as response,
            ):
                if (
                    response.status_code != 200
                    or response.headers.get("content-encoding", "identity").lower()
                    != "identity"
                ):
                    raise ValueError
                body = bytearray()
                for chunk in response.iter_bytes(chunk_size=4096):
                    body.extend(chunk)
                    if len(body) > 65536:
                        raise ValueError
            parsed = json.loads(body)
            if parsed["status"] != "completed":
                raise ValueError
            content = [
                item
                for message in parsed["output"]
                if message.get("type") == "message"
                and message.get("role") == "assistant"
                for item in message["content"]
            ]
            if len(content) != 1 or content[0]["type"] != "output_text":
                raise ValueError
            plan = json.loads(content[0]["text"])
            if set(plan) != set(properties) or any(
                plan[key] not in properties[key]["enum"] for key in properties
            ):
                raise ValueError
            return plan
        except (
            httpx.HTTPError,
            ValueError,
            KeyError,
            TypeError,
            AttributeError,
            RecursionError,
        ):
            raise CoachProviderError(
                "PROVIDER_UNAVAILABLE", "Coach provider did not return a valid choice"
            ) from None

    def explain(self, request: CoachRequest):
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,60}", self.model) or not self.api_key:
            raise CoachProviderError(
                "PROVIDER_UNAVAILABLE", "Coach provider is not configured"
            )
        verified = request.analysis
        ru = request.language == "ru"
        details = verified["facts"]
        facts = {
            "level": request.level,
            "quality": verified["quality"],
            "check": details["checks"],
            "capture": details["captures"],
        }
        available = ["compare"]
        for label in ("check", "capture"):
            if facts[label]:
                available.append(label)
        if request.level in {"candidates", "solution", "detailed"}:
            available.append("engine_preference")
        # No game/analysis/student id, FEN, session, free-text or full move history.
        choice = self.choose(facts, available)
        explanation = RulesCoachProvider().explain(request)
        emphasis = choice["emphasis"]
        why = (
            "Сравните положение фигур до хода и после него."
            if ru
            else "Compare the position of the pieces before and after the move."
        )
        refs, moves = [], [verified["played_move"]]
        if emphasis in {"check", "capture"}:
            claim = next(
                item for item in details["verified_claims"] if item["kind"] == emphasis
            )
            refs.append(claim["fact_id"])
            if emphasis == "check":
                why = (
                    "После этого хода король под шахом."
                    if ru
                    else "After this move, the king is in check."
                )
            else:
                square = claim["evidence"]["square"]
                why = (
                    f"Этим ходом взята фигура на поле {square}."
                    if ru
                    else f"This move captured a piece on {square}."
                )
        if emphasis == "engine_preference":
            best = verified["best_move"]
            why = (
                f"До сыгранного хода движок предпочитал {best}."
                if ru
                else f"Before the played move, the engine preferred {best}."
            )
            moves.append(best)
            refs.append("analysis.best_move")
        explanation.update(
            why=why,
            question=QUESTIONS[choice["question"]][0 if ru else 1],
            referenced_uci=list(dict.fromkeys(moves)),
            highlight_squares=sorted(
                {square for move in moves for square in (move[:2], move[2:4])}
            ),
            claim_refs=refs,
            template_id="verified-choice." + emphasis + ".v1",
            model_id=self.model_id,
        )
        return explanation
