"""Actor-locked learning commands: grading, cursor, receipt and progress commit once."""

import base64
import binascii
from datetime import datetime, timedelta, timezone
import json

from sqlalchemy import and_, delete, func, or_, select

from backend.app.games.durable import DurableGameService, fingerprint, iso
from backend.app.infra.generated import contracts as dto
from backend.app.infra.models import (
    LearningProfileRow,
    LearningReceiptRow,
    LessonRow,
    LessonProgressRow,
    PuzzleRow,
    PuzzleStateRow,
    PuzzleAttemptRow,
    StudentSkillRow,
    ProgressEventRow,
)
from backend.app.infra.problems import PublicProblem
from backend.app.learning import storage
from backend.app.learning.progress_service import (
    ProgressService,
    SkillProgress,
    StudentProgress,
)


def wire(model, payload):
    return model.model_validate(payload).model_dump(mode="json", exclude_none=True)


def aware(value):
    return (
        value if value is None or value.tzinfo else value.replace(tzinfo=timezone.utc)
    )


async def skills(session, student_id, *, due=None):
    query = select(StudentSkillRow).where(StudentSkillRow.student_id == student_id)
    if due is not None:
        query = query.where(StudentSkillRow.due_at <= due)
    rows = list(await session.scalars(query.order_by(StudentSkillRow.skill).limit(101)))
    if len(rows) > 100:
        raise PublicProblem(503)
    return {
        "schema_version": 1,
        "student_id": str(student_id),
        "skills": [storage.skill_payload(r) for r in rows],
    }


async def record_progress(
    session, student_id, tags, event_key, result, now, *, hints_used=0
):
    rows = list(
        await session.scalars(
            select(StudentSkillRow)
            .where(StudentSkillRow.student_id == student_id)
            .limit(101)
        )
    )
    by_skill = {row.skill: row for row in rows}
    if len(by_skill) > 100:
        raise PublicProblem(503)
    domain = ProgressService(now=lambda: now)
    domain.students[str(student_id)] = StudentProgress(
        str(student_id),
        {
            row.skill: SkillProgress(
                row.skill,
                row.attempts,
                row.correct,
                row.hints_used,
                row.streak,
                aware(row.due_at),
            )
            for row in rows
        },
    )
    for tag in dict.fromkeys(tags):
        event_id = fingerprint("learning.progress", {"event": event_key, "skill": tag})
        if await session.get(ProgressEventRow, (student_id, event_id)) is not None:
            continue
        row = by_skill.get(tag)
        if row is None:
            if len(by_skill) >= 100:
                raise PublicProblem(429)
            row = StudentSkillRow(
                student_id=student_id,
                skill=tag,
                attempts=0,
                correct=0,
                hints_used=0,
                streak=0,
            )
            by_skill[tag] = row
            session.add(row)
        if result == "hint":
            progress = domain.record_hint(str(student_id), tag, event_id=event_id)
        else:
            progress = domain.record_server_result(
                str(student_id),
                tag,
                result=result,
                event_id=event_id,
                hints_used=hints_used,
            )
        for field in ("attempts", "correct", "hints_used", "streak", "due_at"):
            setattr(row, field, getattr(progress, field))
        session.add(
            ProgressEventRow(
                student_id=student_id,
                event_id=event_id,
                skill=tag,
                result=result,
                snapshot=storage.skill_payload(row),
                created_at=now,
            )
        )


class DurableLearningService:
    def __init__(self, factory):
        self.factory = factory

    async def read(
        self,
        operation,
        student_id,
        *,
        target=None,
        language="ru",
        page=1,
        page_size=6,
        cursor=None,
    ):
        async with self.factory() as session, session.begin():
            # Snapshot collections and the reset epoch together, including exports.
            await DurableGameService.lock_actor(session, student_id)
            current_epoch = await storage.epoch(session, student_id)
            if operation == "context":
                return {"schema_version": 1, "learning_epoch": current_epoch}
            if operation == "lessons":
                count = await session.scalar(
                    select(func.count()).select_from(LessonRow)
                )
                rows = (
                    await session.execute(
                        select(LessonRow, LessonProgressRow.status)
                        .outerjoin(
                            LessonProgressRow,
                            and_(
                                LessonProgressRow.lesson_id == LessonRow.id,
                                LessonProgressRow.student_id == student_id,
                            ),
                        )
                        .order_by(LessonRow.id)
                        .offset((page - 1) * page_size)
                        .limit(page_size)
                    )
                ).all()
                return wire(
                    dto.LessonListV1,
                    {
                        "schema_version": 1,
                        "learning_epoch": current_epoch,
                        "items": [
                            storage.lesson_payload(row, status, language)
                            for row, status in rows
                        ],
                        "page": page,
                        "total_pages": max(1, (count + page_size - 1) // page_size),
                    },
                )
            if operation == "lesson":
                row = await session.get(LessonRow, target)
                if row is None:
                    raise PublicProblem(404)
                status = await session.get(LessonProgressRow, (student_id, target))
                return storage.lesson_payload(
                    row, status.status if status else None, language
                )
            if operation == "puzzles":
                rows = list(
                    await session.scalars(
                        select(PuzzleRow).order_by(PuzzleRow.id).limit(100)
                    )
                )
                return {
                    "schema_version": 1,
                    "items": [storage.puzzle_payload(row) for row in rows],
                }
            if operation in {"puzzle", "state"}:
                puzzle = await storage.puzzle(session, target)
                if operation == "puzzle":
                    return storage.puzzle_payload(puzzle)
                state, _ = await storage.state(session, student_id, puzzle)
                return storage.state_payload(puzzle, state, current_epoch, language)
            now = await DurableGameService.now(session)
            if operation in {"progress", "review"}:
                return await skills(
                    session, student_id, due=now if operation == "review" else None
                )
            if operation == "export":
                return await self.export(session, student_id, current_epoch, cursor)
            raise ValueError("Unknown learning read")

    async def command(
        self, operation, student_id, key, payload, *, target=None, language="ru"
    ):
        identity = {"target": target, **payload}
        if operation in {"lesson-status", "hint", "restart"}:
            identity["language"] = language
        digest = fingerprint("learning." + operation, identity)
        async with self.factory() as session, session.begin():
            await DurableGameService.lock_actor(session, student_id)
            prior = await session.get(LearningReceiptRow, (student_id, key))
            if prior is not None:
                if prior.request_hash != digest:
                    raise PublicProblem(409)
                return prior.response
            profile = await session.get(LearningProfileRow, student_id)
            if profile is None:
                profile = LearningProfileRow(student_id=student_id, epoch=0)
                session.add(profile)
            if payload["learning_epoch"] != profile.epoch:
                raise PublicProblem(409)
            now = await DurableGameService.now(session)
            recent = await session.scalar(
                select(func.count())
                .select_from(LearningReceiptRow)
                .where(
                    LearningReceiptRow.student_id == student_id,
                    LearningReceiptRow.created_at >= now - timedelta(hours=1),
                )
            )
            if recent >= 600:
                raise PublicProblem(429)
            if operation == "reset":
                for model in (
                    ProgressEventRow,
                    StudentSkillRow,
                    PuzzleAttemptRow,
                    PuzzleStateRow,
                    LessonProgressRow,
                    LearningReceiptRow,
                ):
                    await session.execute(
                        delete(model).where(model.student_id == student_id)
                    )
                if profile.epoch >= 9007199254740991:
                    raise PublicProblem(409)
                profile.epoch += 1
                response = {}
            elif operation == "lesson-status":
                lesson = await session.get(LessonRow, target)
                if lesson is None:
                    raise PublicProblem(404)
                status = await session.get(LessonProgressRow, (student_id, target))
                if status is None:
                    status = LessonProgressRow(
                        student_id=student_id,
                        lesson_id=target,
                        status=payload["status"],
                        updated_at=now,
                    )
                    session.add(status)
                elif status.status != "completed":
                    status.status, status.updated_at = payload["status"], now
                response = storage.lesson_payload(lesson, status.status, language)
            else:
                puzzle = await storage.puzzle(session, target)
                state, grader = await storage.state(
                    session, student_id, puzzle, create=True
                )
                if operation == "attempt":
                    previous = await session.get(
                        PuzzleAttemptRow, (student_id, payload["attempt_id"])
                    )
                    if previous is not None:
                        if previous.request_hash != digest:
                            raise PublicProblem(409)
                        response = previous.response
                    else:
                        if (
                            payload["session_number"] != state.session_number
                            or payload["expected_ply"] != state.cursor
                        ):
                            raise PublicProblem(409)
                        grade = grader.submit(
                            str(student_id),
                            target,
                            attempt_id=payload["attempt_id"],
                            uci=payload["uci"],
                        )
                        response = wire(
                            dto.PuzzleAttemptV1,
                            {
                                k: grade[k]
                                for k in (
                                    "schema_version",
                                    "attempt_id",
                                    "result",
                                    "completed",
                                    "next_ply",
                                )
                            },
                        )
                        if grade["result"] == "correct":
                            state.history = [*state.history, payload["uci"]]
                            state.cursor = grade["next_ply"]
                            state.fen = grader.start(
                                str(student_id), target
                            ).board.fen()
                        state.updated_at = now
                        session.add(
                            PuzzleAttemptRow(
                                student_id=student_id,
                                attempt_id=payload["attempt_id"],
                                puzzle_id=target,
                                uci=payload["uci"],
                                session_number=state.session_number,
                                request_hash=digest,
                                response=response,
                                created_at=now,
                            )
                        )
                        if grade["result"] != "completed":
                            await record_progress(
                                session,
                                student_id,
                                puzzle.tags,
                                "attempt:" + payload["attempt_id"],
                                grade["result"],
                                now,
                                hints_used=state.hints_count - state.hints_accounted,
                            )
                            state.hints_accounted = state.hints_count
                else:
                    if payload["session_number"] != state.session_number:
                        raise PublicProblem(409)
                    if operation == "hint":
                        hints = puzzle.hints[language]
                        if state.hints_count < len(hints):
                            state.hints_count += 1
                            state.hints_accounted = state.hints_count
                            await record_progress(
                                session,
                                student_id,
                                puzzle.tags,
                                "hint:" + str(key),
                                "hint",
                                now,
                            )
                        state.updated_at = now
                        response = wire(
                            dto.PuzzleHintV1,
                            {
                                "schema_version": 1,
                                "puzzle_id": target,
                                "session_number": state.session_number,
                                "hint_index": state.hints_count,
                                "text": hints[state.hints_count - 1],
                                "has_more": state.hints_count < len(hints),
                            },
                        )
                    elif operation == "restart":
                        if state.session_number >= 2147483647:
                            raise PublicProblem(409)
                        state.session_number += 1
                        state.cursor, state.hints_count, state.hints_accounted = 0, 0, 0
                        state.history, state.fen, state.updated_at = [], puzzle.fen, now
                        response = storage.state_payload(
                            puzzle, state, profile.epoch, language
                        )
                    else:
                        raise ValueError("Unknown learning command")
            session.add(
                LearningReceiptRow(
                    student_id=student_id,
                    command_key=key,
                    request_hash=digest,
                    response=response,
                    created_at=now,
                )
            )
            return response

    @staticmethod
    async def export(session, student_id, current_epoch, cursor):
        query = select(PuzzleAttemptRow).where(
            PuzzleAttemptRow.student_id == student_id
        )
        if cursor is not None:
            try:
                data = json.loads(
                    base64.b64decode(
                        cursor + "=" * (-len(cursor) % 4), altchars=b"-_", validate=True
                    )
                )
                if not isinstance(data, list) or len(data) != 3:
                    raise ValueError("Invalid cursor")
                saved_epoch, stamp, attempt_id = data
                if not isinstance(stamp, str) or len(stamp) > 64:
                    raise ValueError("Invalid cursor")
                parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
                if (
                    type(saved_epoch) is not int
                    or not isinstance(attempt_id, str)
                    or len(attempt_id) > 120
                    or parsed.tzinfo is None
                ):
                    raise ValueError("Invalid cursor")
            except (ValueError, TypeError, binascii.Error):
                raise PublicProblem(422) from None
            if saved_epoch != current_epoch:
                raise PublicProblem(409)
            query = query.where(
                or_(
                    PuzzleAttemptRow.created_at > parsed,
                    and_(
                        PuzzleAttemptRow.created_at == parsed,
                        PuzzleAttemptRow.attempt_id > attempt_id,
                    ),
                )
            )
        attempts = list(
            await session.scalars(
                query.order_by(
                    PuzzleAttemptRow.created_at, PuzzleAttemptRow.attempt_id
                ).limit(101)
            )
        )
        next_cursor = None
        if len(attempts) > 100:
            last = attempts[99]
            next_cursor = (
                base64.urlsafe_b64encode(
                    json.dumps(
                        [current_epoch, iso(last.created_at), last.attempt_id]
                    ).encode()
                )
                .decode()
                .rstrip("=")
            )
        lessons = list(
            await session.scalars(
                select(LessonProgressRow)
                .where(LessonProgressRow.student_id == student_id)
                .order_by(LessonProgressRow.lesson_id)
                .limit(1001)
            )
        )
        states = list(
            await session.scalars(
                select(PuzzleStateRow)
                .where(PuzzleStateRow.student_id == student_id)
                .order_by(PuzzleStateRow.puzzle_id)
                .limit(1001)
            )
        )
        if len(lessons) > 1000 or len(states) > 1000:
            raise PublicProblem(429)
        puzzle_states = []
        for state in states:
            row = await storage.puzzle(session, state.puzzle_id)
            validated, _ = await storage.state(session, student_id, row)
            puzzle_states.append(
                storage.state_payload(row, validated, current_epoch, "ru")
            )
        # Keep an explicit null next_cursor and due_at fields required by v1.
        payload = {
            "schema_version": 1,
            "learning_epoch": current_epoch,
            "student_id": str(student_id),
            "progress": await skills(session, student_id),
            "lessons": [
                {"lesson_id": row.lesson_id, "status": row.status} for row in lessons
            ],
            "puzzles": puzzle_states,
            "attempts": [
                {
                    "attempt_id": row.attempt_id,
                    "puzzle_id": row.puzzle_id,
                    "uci": row.uci,
                    "response": row.response,
                    "created_at": iso(row.created_at),
                }
                for row in attempts[:100]
            ],
            "next_cursor": next_cursor,
        }
        dto.LearningExportV1.model_validate(payload)
        return payload
