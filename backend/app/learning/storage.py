"""Validated SQL projections; private puzzle lines never enter pre-attempt DTOs."""

import hashlib

import chess

from backend.app.games.durable import iso
from backend.app.infra.generated.contracts import LessonV1, PuzzleV1, PuzzleStateV1
from backend.app.infra.models import LearningProfileRow, PuzzleRow, PuzzleStateRow
from backend.app.infra.problems import PublicProblem
from backend.app.learning.puzzle_service import Puzzle, PuzzleGrader


async def epoch(session, student_id):
    row = await session.get(LearningProfileRow, student_id)
    return row.epoch if row else 0


def lesson_payload(row, status, language):
    return LessonV1.model_validate(
        {
            "schema_version": 1,
            "id": row.id,
            **row.content[language],
            "language": language,
            "status": status or "not-started",
            "tags": row.tags,
            "source_name": row.source_name,
            "source_url": row.source_url,
            "license": row.license,
        }
    ).model_dump(mode="json")


def puzzle_payload(row):
    return PuzzleV1.model_validate(
        {
            "schema_version": 1,
            "id": row.id,
            "fen": row.fen,
            "difficulty": row.difficulty,
            "tags": row.tags,
            "source_name": row.source_name,
            "source_url": row.source_url,
            "license": row.license,
        }
    ).model_dump(mode="json")


async def puzzle(session, puzzle_id):
    row = await session.get(PuzzleRow, puzzle_id)
    if row is None:
        raise PublicProblem(404)
    try:
        board = chess.Board(row.fen)
        if (
            not board.is_valid()
            or board.fen() != row.fen
            or not 1 <= len(row.private_solution) <= 128
        ):
            raise ValueError("Invalid persisted puzzle")
        digest = hashlib.sha256(
            (row.fen + "|" + " ".join(row.private_solution)).encode()
        ).hexdigest()
        if digest != row.solution_digest:
            raise ValueError("Invalid persisted solution digest")
        for uci in row.private_solution:
            board.push_uci(uci)
        if "mate" in row.tags and not board.is_checkmate():
            raise ValueError("Invalid persisted mate goal")
        for language in ("ru", "en"):
            hints = row.hints[language]
            if not 1 <= len(hints) <= 3 or any(
                not isinstance(h, str) or not 1 <= len(h) <= 500 for h in hints
            ):
                raise ValueError("Invalid persisted hints")
        if len(row.hints["ru"]) != len(row.hints["en"]):
            raise ValueError("Hints must have equivalent language stages")
    except (KeyError, TypeError, ValueError):
        raise PublicProblem(503) from None
    return row


async def state(session, student_id, row, *, create=False):
    stored = await session.get(PuzzleStateRow, (student_id, row.id))
    if stored is None:
        stored = PuzzleStateRow(
            student_id=student_id,
            puzzle_id=row.id,
            fen=row.fen,
            history=[],
            cursor=0,
            hints_count=0,
            hints_accounted=0,
            session_number=0,
        )
        if create:
            session.add(stored)
    domain = Puzzle(
        row.id,
        row.fen,
        tuple(row.private_solution),
        row.difficulty,
        tuple(row.tags),
        row.source_name,
        row.source_url,
        row.license,
    )
    grader = PuzzleGrader({row.id: domain})
    principal = str(student_id)
    cursor = grader.start(principal, row.id)
    try:
        if not isinstance(stored.history, list) or len(stored.history) > len(
            row.private_solution
        ):
            raise ValueError("Invalid persisted puzzle history")
        for index, uci in enumerate(stored.history):
            verdict = grader.submit(
                principal, row.id, attempt_id=f"replay-{index}", uci=uci
            )
            if verdict["result"] != "correct":
                raise ValueError("Invalid persisted puzzle history")
        if (
            cursor.solution_index != stored.cursor
            or cursor.board.fen() != stored.fen
            or not 0 <= stored.hints_count <= len(row.hints["ru"])
        ):
            raise ValueError("Invalid persisted puzzle cursor")
    except (TypeError, ValueError):
        raise PublicProblem(503) from None
    # Replay identifiers are internal and must not collide with a public attempt_id.
    cursor.attempts.clear()
    return stored, grader


def state_payload(row, stored, learning_epoch, language):
    completed = stored.cursor == len(row.private_solution)
    value = {
        "schema_version": 1,
        "learning_epoch": learning_epoch,
        "puzzle_id": row.id,
        "session_number": stored.session_number,
        "current_fen": stored.fen,
        "next_ply": stored.cursor,
        "completed": completed,
        "hints": row.hints[language][: stored.hints_count],
    }
    if completed:
        board, replay = chess.Board(row.fen), []
        for uci in stored.history:
            move = chess.Move.from_uci(uci)
            san = board.san(move)
            board.push(move)
            replay.append({"uci": uci, "san": san, "fen": board.fen()})
        value["solution"] = replay
    return PuzzleStateV1.model_validate(value).model_dump(
        mode="json", exclude_none=True
    )


def skill_payload(row):
    return {
        "skill": row.skill,
        "attempts": row.attempts,
        "correct": row.correct,
        "hints_used": row.hints_used,
        "streak": row.streak,
        "due_at": iso(row.due_at) if row.due_at else None,
    }
