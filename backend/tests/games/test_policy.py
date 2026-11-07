from __future__ import annotations

from uuid import uuid4

import pytest

from backend.app.games.policy import (
    AccessDenied,
    AccessPolicy,
    AccessSnapshot,
    GameMode,
)


def snapshot(mode, status="active"):
    actor = uuid4()
    return AccessSnapshot(mode, status, 0, frozenset({actor})), actor


@pytest.mark.parametrize("mode", [GameMode.FRIEND, GameMode.RATED])
def test_live_pvp_denies_analysis_and_takeback(mode):
    state, actor = snapshot(mode)
    with pytest.raises(AccessDenied):
        AccessPolicy.require_analysis(state, actor)
    with pytest.raises(AccessDenied):
        AccessPolicy.require_takeback(state, actor)


def test_finished_pvp_allows_analysis_but_not_takeback():
    state, actor = snapshot(GameMode.FRIEND, "finished")
    AccessPolicy.require_analysis(state, actor)
    with pytest.raises(AccessDenied):
        AccessPolicy.require_takeback(state, actor)
