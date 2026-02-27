"""Integration tests for organizer context queue updates and player support."""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient


def create_test_session(
    session_id: str = "test-session-123",
    playlist_id: int = 1,
    status: str = "active",
    assigned_track_ids: list[int] = None,
    all_track_ids: list[int] = None
) -> dict:
    """Generate mock bucket session for testing."""
    assigned = assigned_track_ids or []
    all_tracks = all_track_ids or [1, 2, 3, 4, 5]
    unassigned = [tid for tid in all_tracks if tid not in assigned]

    return {
        "id": session_id,
        "playlist_id": playlist_id,
        "status": status,
        "unassigned_track_ids": unassigned,
        "buckets": []  # Not needed for queue tests
    }


@pytest.mark.asyncio
async def test_queue_update_removes_assigned_track():
    """Assigning a track should remove it from queue in real-time."""
    from backend.routers.player import update_organizer_queue, _playback_state

    # Setup initial queue with tracks 1,2,3
    _playback_state.queue = [
        {"id": 1, "title": "Track 1"},
        {"id": 2, "title": "Track 2"},
        {"id": 3, "title": "Track 3"}
    ]
    _playback_state.current_track = {"id": 1, "title": "Track 1"}
    _playback_state.queue_index = 0
    _playback_state.current_context = MagicMock(
        type="organizer",
        session_id="test-session-123"
    )

    # Mock playback state getter to return organizer context
    mock_state = {
        "context": {
            "type": "organizer",
            "session_id": "test-session-123"
        },
        "queue": _playback_state.queue,
        "current_track": _playback_state.current_track
    }

    # Mock session after assigning track 2
    mock_session = create_test_session(
        all_track_ids=[1, 2, 3],
        assigned_track_ids=[2]  # Track 2 now assigned
    )

    with patch("backend.routers.player.get_playback_state", return_value=mock_state), \
         patch("backend.queries.buckets.get_session_with_data", return_value=mock_session), \
         patch("backend.routers.player.sync_manager.broadcast", new_callable=AsyncMock):

        await update_organizer_queue("test-session-123")

    # Queue should now only have tracks 1 and 3
    assert len(_playback_state.queue) == 2
    assert _playback_state.queue[0]["id"] == 1
    assert _playback_state.queue[1]["id"] == 3
    assert all(t["id"] != 2 for t in _playback_state.queue)


@pytest.mark.asyncio
async def test_queue_update_adds_unassigned_track():
    """Unassigning a track should add it back to queue in real-time."""
    from backend.routers.player import update_organizer_queue, _playback_state
    from backend.schemas import PlayContext

    # Setup queue missing track 2 (was assigned)
    _playback_state.queue = [
        {"id": 1, "title": "Track 1"},
        {"id": 3, "title": "Track 3"}
    ]
    _playback_state.current_track = {"id": 1}
    _playback_state.queue_index = 0
    _playback_state.current_context = PlayContext(
        type="organizer",
        playlist_id=1,
        session_id="test-session-123"
    )

    mock_state = {
        "context": {
            "type": "organizer",
            "session_id": "test-session-123"
        },
        "queue": _playback_state.queue,
        "current_track": {"id": 1}
    }

    # Mock session after unassigning track 2
    mock_session = create_test_session(
        all_track_ids=[1, 2, 3],
        assigned_track_ids=[]  # Track 2 now unassigned
    )

    with patch("backend.routers.player.get_playback_state", return_value=mock_state), \
         patch("backend.queries.buckets.get_session_with_data", return_value=mock_session), \
         patch("backend.queries.tracks.batch_fetch_tracks_with_metadata", return_value=[{"id": 2, "title": "Track 2"}]), \
         patch("backend.routers.player.sync_manager.broadcast", new_callable=AsyncMock):

        await update_organizer_queue("test-session-123")

    # Track 2 should now be in queue (appended to end)
    assert len(_playback_state.queue) == 3
    queue_ids = [t["id"] for t in _playback_state.queue]
    assert 2 in queue_ids
    # Original tracks still present
    assert 1 in queue_ids
    assert 3 in queue_ids


@pytest.fixture
def client():
    """Create FastAPI test client."""
    from backend.main import app
    return TestClient(app)


def test_play_endpoint_rejects_invalid_organizer_session(client):
    """Play endpoint should validate organizer session exists and is active."""
    from unittest.mock import patch

    # Test missing session
    with patch("backend.queries.buckets.get_session_with_data", return_value=None):
        response = client.post("/api/player/play", json={
            "trackId": 1,
            "context": {
                "type": "organizer",
                "playlistId": 1,
                "sessionId": "nonexistent-session"
            }
        })
        assert response.status_code == 404

    # Test inactive session
    mock_session = create_test_session(status="applied")
    with patch("backend.queries.buckets.get_session_with_data", return_value=mock_session):
        response = client.post("/api/player/play", json={
            "trackId": 1,
            "context": {
                "type": "organizer",
                "playlistId": 1,
                "sessionId": "test-session-123"
            }
        })
        assert response.status_code == 400
        assert "applied" in response.json()["detail"].lower()
