"""Tests for organizer queue behavior in player router."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from web.backend.player_state import PlaybackState
import web.backend.queries.buckets  # noqa: F401  ensure submodule loaded for patch targets
import web.backend.queries.tracks  # noqa: F401
from web.backend.routers.player import advance_queue, update_organizer_queue
from web.backend.schemas import PlayContext


def _track(track_id: int) -> dict:
    return {"id": track_id, "title": f"Track {track_id}", "source": "local"}


def _session(all_track_ids: list[int], assigned: list[int] | None = None) -> dict:
    assigned = assigned or []
    unassigned = [tid for tid in all_track_ids if tid not in assigned]
    return {
        "id": "test-session-123",
        "playlist_id": 1,
        "status": "active",
        "unassigned_track_ids": unassigned,
        "buckets": [],
    }


# ---------- update_organizer_queue: forward survivor lookup ----------


@pytest.mark.asyncio
async def test_assign_current_advances_to_next_forward() -> None:
    """T1: Assigning current track sets queue_index to next forward survivor."""
    initial_state = PlaybackState(
        queue=tuple(_track(i) for i in [1, 2, 3, 4, 5]),
        current_track=_track(4),
        queue_index=3,
        current_context=PlayContext(type="organizer", playlist_id=1, session_id="test-session-123"),
    )
    session = _session([1, 2, 3, 4, 5], assigned=[4])

    mock_db_conn = MagicMock()
    mock_db_conn.__enter__ = MagicMock(return_value=mock_db_conn)
    mock_db_conn.__exit__ = MagicMock(return_value=False)

    with patch("web.backend.routers.player.get_state", return_value=initial_state), \
         patch("web.backend.queries.buckets.get_session_with_data", return_value=session), \
         patch("web.backend.routers.player.update_state", new_callable=AsyncMock) as mock_update, \
         patch("music_minion.core.database.get_db_connection", return_value=mock_db_conn):

        await update_organizer_queue("test-session-123")

    update_call = mock_update.call_args[0][0]
    updated_queue = update_call["queue"]
    assert [t["id"] for t in updated_queue] == [1, 2, 3, 5]
    # Position of t5 in updated_queue is 3 — advance_queue will play queue[3] without +1
    # because current_track (t4) is no longer in queue at queue_index.
    assert update_call["queue_index"] == 3


@pytest.mark.asyncio
async def test_assign_with_no_forward_survivors_advances_to_end_of_queue() -> None:
    """T2: Assigning the last track sets queue_index to len(queue) so end-of-queue path fires."""
    initial_state = PlaybackState(
        queue=tuple(_track(i) for i in [1, 2, 3]),
        current_track=_track(3),
        queue_index=2,
        current_context=PlayContext(type="organizer", playlist_id=1, session_id="test-session-123"),
    )
    session = _session([1, 2, 3], assigned=[3])

    mock_db_conn = MagicMock()
    mock_db_conn.__enter__ = MagicMock(return_value=mock_db_conn)
    mock_db_conn.__exit__ = MagicMock(return_value=False)

    with patch("web.backend.routers.player.get_state", return_value=initial_state), \
         patch("web.backend.queries.buckets.get_session_with_data", return_value=session), \
         patch("web.backend.routers.player.update_state", new_callable=AsyncMock) as mock_update, \
         patch("music_minion.core.database.get_db_connection", return_value=mock_db_conn):

        await update_organizer_queue("test-session-123")

    update_call = mock_update.call_args[0][0]
    updated_queue = update_call["queue"]
    assert [t["id"] for t in updated_queue] == [1, 2]
    # No forward survivors → queue_index points past end so advance_queue stops playback.
    assert update_call["queue_index"] == len(updated_queue)


# ---------- advance_queue: displaced detection ----------


def test_advance_queue_normal_skip_preserves_plus_one() -> None:
    """T4 REGRESSION: when current_track matches queue[queue_index], advance does +1."""
    state = PlaybackState(
        queue=tuple(_track(i) for i in [1, 2, 3]),
        current_track=_track(1),
        queue_index=0,
        current_context=PlayContext(type="playlist", playlist_id=1),
    )

    with patch("music_minion.domain.radio.history.start_play", return_value=42):
        new_state = advance_queue(state)

    assert new_state.queue_index == 1
    assert new_state.current_track["id"] == 2


def test_advance_queue_displaced_current_no_plus_one() -> None:
    """T5: when current_track is NOT at queue[queue_index] (displaced), advance plays queue[queue_index]."""
    state = PlaybackState(
        queue=tuple(_track(i) for i in [2, 3]),  # t1 was filtered out
        current_track=_track(1),  # still pointing at displaced t1
        queue_index=0,
        current_context=PlayContext(type="organizer", playlist_id=1, session_id="s1"),
    )

    with patch("music_minion.domain.radio.history.start_play", return_value=42):
        new_state = advance_queue(state)

    assert new_state.queue_index == 0  # NOT +1
    assert new_state.current_track["id"] == 2


def test_advance_queue_end_of_queue_stops_playback() -> None:
    """advance_queue returns is_playing=False when past end of queue."""
    state = PlaybackState(
        queue=tuple(_track(i) for i in [1, 2]),
        current_track=_track(2),
        queue_index=1,
        is_playing=True,
        current_context=PlayContext(type="playlist", playlist_id=1),
    )

    new_state = advance_queue(state)

    assert new_state.is_playing is False
    assert new_state.current_track is None


# ---------- next_track: refill exclusion ----------


def _capture_refill_exclusion(queue_size: int, qi: int) -> list[int]:
    """Drive the /next refill path for a playlist context; capture exclusion_ids."""
    from fastapi.testclient import TestClient
    from web.backend.main import app

    queue = tuple(_track(i) for i in range(1, queue_size + 1))
    ctx = PlayContext(type="playlist", playlist_id=1)
    state_advanced = PlaybackState(
        queue=queue,
        current_track=_track(qi + 2),  # after advance_queue +1 from qi
        queue_index=qi + 1,
        current_context=ctx,
        shuffle_enabled=True,
    )
    state_initial = PlaybackState(
        queue=queue,
        current_track=_track(qi + 1),
        queue_index=qi,
        current_context=ctx,
        shuffle_enabled=True,
    )
    captured: dict = {}

    def fake_get_next_tracks(**kwargs):
        captured["exclusion_ids"] = kwargs.get("exclusion_ids")
        return [], None  # nothing new: no append, no cursor move

    state_calls = [state_initial, state_advanced, state_advanced, state_advanced]

    def get_state_side_effect():
        return state_calls.pop(0) if state_calls else state_advanced

    with patch("web.backend.routers.player.get_state", side_effect=get_state_side_effect), \
         patch("web.backend.routers.player.update_state", new_callable=AsyncMock), \
         patch("web.backend.routers.player.get_next_tracks", side_effect=fake_get_next_tracks), \
         patch("web.backend.routers.player.save_queue_state"), \
         patch("web.backend.routers.player._calculate_final_duration", return_value=0), \
         patch("music_minion.domain.radio.history.end_play"), \
         patch("music_minion.domain.radio.history.start_play", return_value=42):
        TestClient(app).post("/api/player/next")

    assert "exclusion_ids" in captured, "get_next_tracks was not called; refill path didn't fire"
    return captured["exclusion_ids"]


def test_playlist_refill_excludes_forward_only() -> None:
    """Rolling-window refill excludes only the tracks still ahead of the cursor."""
    # qi advances from 2 to 3 -> queue[3:] = 48 entries, below REFILL_THRESHOLD
    exclusion = _capture_refill_exclusion(queue_size=51, qi=2)
    assert exclusion == list(range(4, 52))
