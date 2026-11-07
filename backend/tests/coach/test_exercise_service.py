from backend.app.learning.exercise_service import ExerciseService, VerifiedMistake


VALID = VerifiedMistake("game-1", "student-1", 3, "6k1/5ppp/8/8/8/8/5PPP/3R2K1 w - - 0 1", "back-rank", True, "pvp", ("d1d8",), True, True, "analysis-1")


def test_only_verified_owned_pvp_mistake_generates_exercise():
    service = ExerciseService()
    exercise = service.from_mistake("student-1", VALID)
    assert exercise is not None
    assert exercise.tags == ("back-rank",)


def test_invalid_or_unowned_mistakes_are_rejected_and_fallback_is_curated():
    service = ExerciseService()
    assert service.from_mistake("other", VALID) is None
    assert service.from_mistake("student-1", VerifiedMistake(**{**VALID.__dict__, "motif_verified": False})) is None
    assert service.from_mistake("student-1", VerifiedMistake(**{**VALID.__dict__, "solution_uci": ("a1a9",)})) is None
    assert service.fallback().id == "back-rank"


def test_generation_is_deduplicated():
    service = ExerciseService()
    assert service.from_mistake("student-1", VALID) is service.from_mistake("student-1", VALID)


def test_unfinished_or_unverified_source_is_rejected():
    service = ExerciseService()
    assert service.from_mistake("student-1", VerifiedMistake(**{**VALID.__dict__, "source_finished": False})) is None
    assert service.from_mistake("student-1", VerifiedMistake(**{**VALID.__dict__, "verified_by_server": False})) is None
