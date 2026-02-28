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
    from backend.routers.player import update_organizer_queue
    from backend.player_state import PlaybackState
    from asyncio import Lock
    from unittest.mock import MagicMock

    # Create initial state
    initial_state = PlaybackState(
        queue=(
            {"id": 1, "title": "Track 1"},
            {"id": 2, "title": "Track 2"},
            {"id": 3, "title": "Track 3"}
        ),
        current_track={"id": 1, "title": "Track 1"},
        queue_index=0,
        current_context={
            "type": "organizer",
            "session_id": "test-session-123"
        }
    )

    # Mock session after assigning track 2
    mock_session = create_test_session(
        all_track_ids=[1, 2, 3],
        assigned_track_ids=[2]  # Track 2 now assigned
    )

    # Use a real Lock object for async with
    real_lock = Lock()

    # Mock database connection
    mock_db_conn = MagicMock()
    mock_db_conn.__enter__ = MagicMock(return_value=mock_db_conn)
    mock_db_conn.__exit__ = MagicMock(return_value=False)

    with patch("backend.player_state.get_state", return_value=initial_state), \
         patch("backend.queries.buckets.get_session_with_data", return_value=mock_session), \
         patch("backend.player_state.update_state", new_callable=AsyncMock) as mock_update, \
         patch("backend.routers.player._next_lock", real_lock), \
         patch("music_minion.core.database.get_db_connection", return_value=mock_db_conn):

        await update_organizer_queue("test-session-123")

    # Verify update_state was called with filtered queue
    mock_update.assert_called_once()
    update_call_args = mock_update.call_args[0][0]
    updated_queue = update_call_args["queue"]

    # Queue should now only have tracks 1 and 3
    assert len(updated_queue) == 2
    assert updated_queue[0]["id"] == 1
    assert updated_queue[1]["id"] == 3
    assert all(t["id"] != 2 for t in updated_queue)


@pytest.mark.asyncio
async def test_queue_update_adds_unassigned_track():
    """Unassigning a track should add it back to queue in real-time."""
    from backend.routers.player import update_organizer_queue
    from backend.player_state import PlaybackState
    from asyncio import Lock
    from unittest.mock import MagicMock

    # Create initial state - queue missing track 2 (was assigned)
    initial_state = PlaybackState(
        queue=(
            {"id": 1, "title": "Track 1"},
            {"id": 3, "title": "Track 3"}
        ),
        current_track={"id": 1},
        queue_index=0,
        current_context={
            "type": "organizer",
            "playlist_id": 1,
            "session_id": "test-session-123"
        }
    )

    # Mock session after unassigning track 2
    mock_session = create_test_session(
        all_track_ids=[1, 2, 3],
        assigned_track_ids=[]  # Track 2 now unassigned
    )

    # Use a real Lock object for async with
    real_lock = Lock()

    # Mock database connection
    mock_db_conn = MagicMock()
    mock_db_conn.__enter__ = MagicMock(return_value=mock_db_conn)
    mock_db_conn.__exit__ = MagicMock(return_value=False)

    with patch("backend.player_state.get_state", return_value=initial_state), \
         patch("backend.queries.buckets.get_session_with_data", return_value=mock_session), \
         patch("backend.queries.tracks.batch_fetch_tracks_with_metadata", return_value=[{"id": 2, "title": "Track 2"}]), \
         patch("backend.player_state.update_state", new_callable=AsyncMock) as mock_update, \
         patch("backend.routers.player._next_lock", real_lock), \
         patch("music_minion.core.database.get_db_connection", return_value=mock_db_conn):

        await update_organizer_queue("test-session-123")

    # Verify update_state was called with track 2 added
    mock_update.assert_called_once()
    update_call_args = mock_update.call_args[0][0]
    updated_queue = update_call_args["queue"]

    # Track 2 should now be in queue (appended to end)
    assert len(updated_queue) == 3
    queue_ids = [t["id"] for t in updated_queue]
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
