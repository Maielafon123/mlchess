"""Async SQL reader with an explicit principal; no client facts or global actor."""

from uuid import UUID

from backend.app.analysis.durable import require_analysis
from backend.app.analysis.service import reconstruct_position
from backend.app.coach.grounding import AnalysisFacts
from backend.app.coach.providers.base import CoachRequest
from backend.app.games.durable import DurableGameService, decode_domain
from backend.app.infra.generated.contracts import AnalysisResultV1
from backend.app.infra.models import Analysis, WorkerJob
from backend.app.infra.problems import PublicProblem


async def read_verified(session, actor_id, request: CoachRequest, *, lock=True):
    game, state, _ = await DurableGameService.load(
        session, UUID(request.game_id), actor_id, lock=lock
    )
    require_analysis(game)
    if game.revision != request.revision:
        raise PublicProblem(409)
    row = await session.get(Analysis, UUID(request.analysis_id))
    job = await session.get(WorkerJob, UUID(request.analysis_id))
    if row is None or row.game_id != game.id:
        raise PublicProblem(404)
    if row.revision != request.revision or row.ply != request.ply:
        raise PublicProblem(409)
    if job is None or job.status != "done" or row.status != "done":
        raise PublicProblem(409)
    result = AnalysisResultV1.model_validate(row.result).model_dump(mode="json")
    try:
        slice_ = reconstruct_position(decode_domain(state.domain), row.ply)
    except ValueError:
        raise PublicProblem(409) from None
    if (
        result["analysis_id"],
        result["game_id"],
        result["revision"],
        result["ply"],
        result["position_key"],
        result["before_fen"],
        result["after_fen"],
    ) != (
        str(row.id),
        str(game.id),
        request.revision,
        request.ply,
        slice_.position_key,
        slice_.before.fen(),
        slice_.after.fen(),
    ):
        raise PublicProblem(409)
    return game, state, result


def grounded_request(request: CoachRequest, result: dict):
    from dataclasses import replace

    moves = list(
        dict.fromkeys(
            [
                result["played_move_uci"],
                result["best_move_uci"],
                *[m["uci"] for m in result["top_moves"]],
            ]
        )
    )[:8]
    squares = sorted({square for move in moves for square in (move[:2], move[2:4])})
    refs = {
        "analysis.best_move",
        "analysis.quality",
        *[c["fact_id"] for c in result["facts"]["verified_claims"]],
    }
    data = {
        "played_move": result["played_move_uci"],
        "best_move": result["best_move_uci"],
        "quality": result["quality"],
        "referenced_uci": moves,
        "highlight_squares": squares,
        "claim_refs": sorted(refs),
        "facts": result["facts"],
    }
    facts = AnalysisFacts(
        request.game_id,
        request.analysis_id,
        request.revision,
        request.ply,
        frozenset(moves),
        frozenset(squares),
        frozenset(refs),
        any(result[k]["kind"] == "mate" for k in ("score_before", "score_after")),
    )
    return replace(request, analysis=data), facts
