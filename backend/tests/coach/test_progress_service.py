from datetime import datetime, timedelta, timezone

from backend.app.learning.progress_service import ProgressService


def test_schedule_is_deterministic_and_uses_server_result():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    service = ProgressService(now=lambda: now)
    first = service.record_server_result("s1", "back-rank", result="correct", hints_used=1)
    assert first.correct == 1
    assert first.due_at == now + timedelta(days=1)
    assert service.review_queue("s1") == []
    now = now + timedelta(days=1)
    assert [item.skill for item in service.review_queue("s1")] == ["back-rank"]


def test_incorrect_and_illegal_do_not_award_correct_progress():
    service = ProgressService()
    service.record_server_result("s1", "back-rank", result="incorrect")
    skill = service.record_server_result("s1", "back-rank", result="illegal")
    assert skill.correct == 0
    assert skill.streak == 0


def test_export_and_delete_boundaries():
    service = ProgressService()
    service.record_server_result("s1", "opening", result="correct")
    assert service.export("s1")["student_id"] == "s1"
    service.delete("s1")
    assert service.export("s1")["skills"] == []
