"""Worker-only analysis and chess-rule facts, with White POV throughout."""

from dataclasses import asdict
from uuid import uuid4

import chess

from backend.app.analysis.durable import LEVELS
from backend.app.analysis.service import quality_from_cp_loss
from backend.app.engine.adapter import EngineBudget, EngineError, EngineScore
from backend.app.infra.generated.contracts import AnalysisResultV1

VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
}


def score_json(score):
    if score.pov != "white" or (score.cp is None) == (score.mate is None):
        raise EngineError("Analysis requires a White POV score")
    value = score.cp if score.cp is not None else score.mate
    if type(value) is not int:
        raise EngineError("Analysis score must be integral")
    return {
        "kind": "cp" if score.cp is not None else "mate",
        "value": value,
        "pov": "white",
    }


def facts(slice_):
    before, after = slice_.before, slice_.after
    move = chess.Move.from_uci(slice_.move.uci)
    claims, motifs = [], []

    def claim(kind, **evidence):
        claims.append(
            {
                "fact_id": str(uuid4()),
                "kind": kind,
                "evidence": {"uci": move.uci(), **evidence},
            }
        )

    if after.is_check():
        claim("check", after_fen=after.fen())
    if after.is_checkmate():
        motifs.append("checkmate")
        claim(
            "checkmate",
            after_fen=after.fen(),
            winner="white" if before.turn else "black",
        )
    if before.is_capture(move):
        square = move.to_square
        if before.is_en_passant(move):
            square += -8 if before.turn else 8
        claim(
            "capture",
            captured_piece=chess.piece_name(before.piece_at(square).piece_type),
            square=chess.square_name(square),
        )
    if move.promotion:
        motifs.append("promotion")
        claim("promotion", promoted_piece=chess.piece_name(move.promotion))
    if before.is_en_passant(move):
        motifs.append("en_passant")
    if before.is_castling(move):
        motifs.append("castling")

    def balance(board):
        return sum(
            value
            * (
                len(board.pieces(piece, before.turn))
                - len(board.pieces(piece, not before.turn))
            )
            for piece, value in VALUES.items()
        )

    return {
        "checks": after.is_check(),
        "captures": before.is_capture(move),
        "material_delta": balance(after) - balance(before),
        "motifs_verified": motifs,
        "verified_claims": claims,
    }


def evaluate(
    engine, slice_, *, analysis_id, game_id, revision, level, metadata, created_at
):
    budget = EngineBudget(**LEVELS[level])
    multipv = min(3, slice_.before.legal_moves.count())
    lines = engine.analyze(slice_.before, budget=budget, multipv=multipv)
    if len(lines) != multipv or len({line.uci for line in lines}) != multipv:
        raise EngineError("Incomplete or duplicate candidates")
    top_moves = []
    for line in lines:
        if (
            not line.pv_uci
            or not 1 <= len(line.pv_uci) <= 128
            or line.pv_uci[0] != line.uci
        ):
            raise EngineError("Invalid principal variation")
        replay = slice_.before.copy(stack=True)
        move = chess.Move.from_uci(line.uci)
        if move not in replay.legal_moves or replay.san(move) != line.san:
            raise EngineError("Invalid candidate")
        for uci in line.pv_uci:
            move = chess.Move.from_uci(uci)
            if move not in replay.legal_moves:
                raise EngineError("Illegal principal variation")
            replay.push(move)
        top_moves.append(
            {
                "uci": line.uci,
                "san": line.san,
                "pv_uci": list(line.pv_uci),
                "score": score_json(line.score),
            }
        )
    outcome = slice_.after.outcome(claim_draw=False)
    if any(
        line["score"]["kind"] == "mate" and line["score"]["value"] == 0
        for line in top_moves
    ):
        raise EngineError("Candidate mate zero requires a terminal input position")
    if slice_.after.is_checkmate():
        after_score = EngineScore("white", mate=0)
    elif outcome is not None:
        after_score = EngineScore("white", cp=0)
    else:
        after_score = engine.analyze(slice_.after, budget=budget, multipv=1)[0].score
    before_score, after_score = top_moves[0]["score"], score_json(after_score)
    if (
        after_score["kind"] == "mate"
        and after_score["value"] == 0
        and not slice_.after.is_checkmate()
    ):
        raise EngineError("Mate zero requires a checkmated position")
    mate = any(item["kind"] == "mate" for item in (before_score, after_score))
    loss = (
        None
        if mate
        else max(
            0,
            (before_score["value"] - after_score["value"])
            * (1 if slice_.before.turn else -1),
        )
    )
    result = {
        "schema_version": 1,
        "analysis_id": str(analysis_id),
        "game_id": str(game_id),
        "revision": revision,
        "ply": slice_.ply,
        "position_key": slice_.position_key,
        "before_fen": slice_.before.fen(),
        "after_fen": slice_.after.fen(),
        "played_move_uci": slice_.move.uci,
        "best_move_uci": top_moves[0]["uci"],
        "top_moves": top_moves,
        "score_before": before_score,
        "score_after": after_score,
        "quality": quality_from_cp_loss(loss, mate=mate),
        "quality_method": "mate-score-v1" if mate else "cp-loss-v1",
        "cp_loss": loss,
        "engine": {
            **metadata,
            "limits": asdict(budget),
            "multipv": multipv,
            "threads": 1,
            "hash_mb": 32,
        },
        "facts": facts(slice_),
        "created_at": created_at,
    }
    return AnalysisResultV1.model_validate(result).model_dump(mode="json")
