"""Deterministic Student Progress and spaced repetition service (B-022)."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable


@dataclass
class SkillProgress:
    skill: str
    attempts: int = 0
    correct: int = 0
    hints_used: int = 0
    streak: int = 0
    due_at: datetime | None = None


@dataclass
class StudentProgress:
    student_id: str
    skills: dict[str, SkillProgress] = field(default_factory=dict)


class ProgressService:
    intervals = (timedelta(days=1), timedelta(days=3), timedelta(days=7))

    def __init__(self, *, now: Callable[[], datetime] | None = None):
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.students: dict[str, StudentProgress] = {}

    def get(self, student_id: str) -> StudentProgress:
        return self.students.setdefault(student_id, StudentProgress(student_id))

    def record_server_result(self, student_id: str, skill: str, *, result: str, hints_used: int = 0) -> SkillProgress:
        """Only server grader results may award progress; client booleans are absent."""
        if result not in {"correct", "incorrect", "illegal"}:
            raise ValueError("unsupported server result")
        progress = self.get(student_id).skills.setdefault(skill, SkillProgress(skill))
        progress.attempts += 1
        progress.hints_used += max(0, hints_used)
        if result == "correct":
            progress.correct += 1
            progress.streak += 1
            progress.due_at = self.now() + self.intervals[min(progress.streak - 1, len(self.intervals) - 1)]
        else:
            progress.streak = 0
            progress.due_at = self.now()
        return progress

    def review_queue(self, student_id: str) -> list[SkillProgress]:
        now = self.now()
        return [skill for skill in self.get(student_id).skills.values() if skill.due_at is not None and skill.due_at <= now]

    def export(self, student_id: str) -> dict:
        student = self.get(student_id)
        return {"student_id": student.student_id, "skills": [{"skill": item.skill, "attempts": item.attempts, "correct": item.correct, "hints_used": item.hints_used, "streak": item.streak, "due_at": item.due_at.isoformat() if item.due_at else None} for item in student.skills.values()]}

    def delete(self, student_id: str) -> None:
        self.students.pop(student_id, None)
