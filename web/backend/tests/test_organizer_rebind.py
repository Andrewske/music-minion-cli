"""Rebinding live organizer playback when the loaded session changes."""

from asyncio import Lock
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from web.backend.player_state import PlaybackState
from web.backend.routers.player import _rebound_queue, rebind_organizer_session
from web.backend.schemas import PlayContext

OLD, NEW = "old-session", "new-session"


def _state(session_id: str = OLD, playlist_id: int = 1) -> PlaybackState:
    return PlaybackState(
        queue=({"id": 10}, {"id": 11}, {"id": 12}),
        current_track={"id": 11},
        queue_index=1,
        is_playing=True,
        position_ms=42_000,
        current_context=PlayContext(
            type="organizer",
            playlist_id=playlist_id,
            session_id=session_id,
            bucket_id="b-old",
        ),
    )


def _session(status: str = "active", playlist_id: int = 1) -> dict:
    return {
        "id": NEW,
        "playlist_id": playlist_id,
        "status": status,
        "unassigned_track_ids": [1, 2, 11],
        "buckets": [],
    }


async def _rebind(
    state: PlaybackState, target: dict | None
) -> tuple[bool, AsyncMock, MagicMock]:
    with (
        patch("web.backend.routers.player.get_state", return_value=state),
        patch("web.backend.queries.buckets.get_session_with_data", return_value=target),
        patch("web.backend.routers.player.initialize_queue", return_value=[1, 2, 11]),
        patch(
            "web.backend.queries.tracks.batch_fetch_tracks_with_metadata",
            side_effect=lambda ids, _db: [{"id": i} for i in ids],
        ),
        patch(
            "web.backend.routers.player.update_state", new_callable=AsyncMock
        ) as update,
        patch("web.backend.routers.player.save_queue_state") as save,
        patch("web.backend.routers.player._player_lock", Lock()),
    ):
        rebound = await rebind_organizer_session(OLD, NEW, MagicMock())
    return rebound, update, save


@pytest.mark.asyncio
async def test_rebind_swaps_session_and_keeps_current_track():
    rebound, update, save = await _rebind(_state(), _session())

    assert rebound is True
    update.assert_awaited_once()
    changes = update.call_args[0][0]
    assert changes["current_context"].session_id == NEW
    assert changes["current_context"].bucket_id is None
    assert [t["id"] for t in changes["queue"]] == [11, 1, 2]
    assert changes["queue_index"] == 0
    # Never restarts the track: position/current_track are left alone.
    assert "position_ms" not in changes and "current_track" not in changes
    assert save.call_args.kwargs["queue_ids"] == [11, 1, 2]
    assert save.call_args.kwargs["context"].session_id == NEW


@pytest.mark.asyncio
async def test_rebind_noop_when_playback_not_bound_to_old_session():
    rebound, update, save = await _rebind(_state(session_id="someone-else"), _session())
    assert rebound is False
    update.assert_not_awaited()
    save.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "target", [None, _session(status="parked"), _session(playlist_id=2)]
)
async def test_rebind_rejects_bad_target(target):
    rebound, update, _save = await _rebind(_state(), target)
    assert rebound is False
    update.assert_not_awaited()


def test_rebound_queue_without_current_track_is_just_the_pool():
    assert _rebound_queue(None, [{"id": 1}, {"id": 2}]) == (({"id": 1}, {"id": 2}), 0)


def test_rebind_endpoint_reports_result():
    from fastapi.testclient import TestClient

    from web.backend.main import app

    with patch(
        "web.backend.routers.player.rebind_organizer_session",
        new_callable=AsyncMock,
        return_value=False,
    ) as rebind:
        response = TestClient(app).post(
            "/api/player/organizer/rebind",
            json={"fromSessionId": OLD, "toSessionId": NEW},
        )
    assert response.status_code == 200
    assert response.json() == {"rebound": False}
    assert rebind.await_args.args[:2] == (OLD, NEW)
