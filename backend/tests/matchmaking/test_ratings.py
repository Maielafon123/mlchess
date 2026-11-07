from uuid import uuid4

from backend.app.matchmaking.ratings import Outcome, RatingService


def test_rating_settlement_is_reproducible_and_idempotent():
    service = RatingService()
    game_id, white, black = uuid4(), uuid4(), uuid4()
    first = service.settle(
        game_id=game_id,
        white_id=white,
        black_id=black,
        pool="main",
        outcome=Outcome.WHITE,
    )
    second = service.settle(
        game_id=game_id,
        white_id=white,
        black_id=black,
        pool="main",
        outcome=Outcome.WHITE,
    )
    assert first[0].value > 1200 and first[1].value < 1200
    assert first[0].games_count == 1
    assert second[0].value == first[0].value
