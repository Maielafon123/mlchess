import pytest

from backend.app.learning.puzzle_service import CURATED_PUZZLES, PuzzleGrader


def test_server_ignores_client_correctness_claim_and_grades_solution():
    grader = PuzzleGrader(CURATED_PUZZLES)
    result = grader.submit("student-1", "back-rank", attempt_id="a1", uci="d1d8", is_correct=False)
    assert result["result"] == "correct"
    assert result["completed"] is True


def test_illegal_and_wrong_moves_are_not_progress():
    grader = PuzzleGrader(CURATED_PUZZLES)
    illegal = grader.submit("student-1", "back-rank", attempt_id="a1", uci="a1a9", is_correct=True)
    wrong = grader.submit("student-1", "back-rank", attempt_id="a2", uci="g1f1", is_correct=True)
    assert illegal["result"] == "illegal"
    assert wrong["result"] == "incorrect"
    assert illegal["next_ply"] == wrong["next_ply"] == 0


def test_repeated_attempt_is_idempotent():
    grader = PuzzleGrader(CURATED_PUZZLES)
    first = grader.submit("student-1", "back-rank", attempt_id="same", uci="d1d8")
    repeated = grader.submit("student-1", "back-rank", attempt_id="same", uci="g1f1")
    assert repeated == first


def test_unknown_puzzle_is_rejected():
    with pytest.raises(KeyError):
        PuzzleGrader(CURATED_PUZZLES).start("student-1", "missing")
