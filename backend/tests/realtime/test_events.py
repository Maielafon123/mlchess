from uuid import uuid4

import pytest

from backend.app.realtime.events import CursorError, InMemoryEventStream, StreamDenied


def test_event_sequence_replay_is_ordered_and_acl_checked():
    stream = InMemoryEventStream()
    game_id, actor, stranger = uuid4(), uuid4(), uuid4()
    stream.participants[game_id] = frozenset({actor})
    stream.append(game_id, "game.snapshot", {"version": 0})
    stream.append(game_id, "game.move_committed", {"version": 1})
    stream.authorize(game_id, actor)
    assert [event.seq for event in stream.replay(game_id, after_seq=1)] == [2]
    with pytest.raises(StreamDenied):
        stream.authorize(game_id, stranger)


def test_cursor_ahead_requires_resync():
    stream = InMemoryEventStream()
    game_id = uuid4()
    with pytest.raises(CursorError):
        stream.replay(game_id, after_seq=1)
