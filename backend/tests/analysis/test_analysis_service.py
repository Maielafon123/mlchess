from __future__ import annotations

import pytest

from backend.app.analysis.service import (
    AnalysisError,
    position_key,
    quality_from_cp_loss,
    reconstruct_position,
)
from backend.app.games.domain import GameDomain


def test_reconstruction_uses_full_history_and_canonical_key():
    game = GameDomain.from_history("friend", ["e2e4", "e7e5"])
    slice_ = reconstruct_position(game, 2)
    assert "4P3" in slice_.before.fen().split()[0]
    assert slice_.after.fen() == game.fen
    assert slice_.position_key == position_key(slice_.before.fen(), "e7e5")


def test_invalid_ply_is_rejected():
    with pytest.raises(AnalysisError):
        reconstruct_position(GameDomain.start(), 1)


@pytest.mark.parametrize(
    ("loss", "expected"),
    [
        (0, "best"),
        (40, "good"),
        (100, "inaccuracy"),
        (200, "mistake"),
        (400, "blunder"),
        (None, "unclassified"),
    ],
)
def test_cp_loss_quality_thresholds(loss, expected):
    assert quality_from_cp_loss(loss) == expected
