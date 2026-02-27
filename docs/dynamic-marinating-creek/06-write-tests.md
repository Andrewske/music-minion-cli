---
task: 06-write-tests
status: pending
depends: [02-implement-queue-resolution, 03-real-time-queue-updates, 05-session-validation]
files:
  - path: web/backend/tests/test_queue_manager.py
    action: modify
  - path: web/backend/tests/test_organizer_queue.py
    action: create
---

# Write Automated Tests for Organizer Queue

## Context
Comprehensive test coverage for organizer context queue resolution, loop restart, real-time updates, and session validation. These tests ensure the core functionality works correctly and catch edge cases like the loop restart bug.

## Files to Modify/Create
- web/backend/tests/test_queue_manager.py (modify) - Add queue resolution tests
- web/backend/tests/test_organizer_queue.py (create) - Integration tests for full organizer flow

## Test Setup

### Mock Bucket Session Data

Create helper function for generating test session data:

```python
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
```

## Unit Tests (test_queue_manager.py)

### Test 1: Resolve Organizer Context

```python
def test_resolve_organizer_context_returns_only_unassigned(test_db):
    """Queue should only contain unassigned tracks from bucket session."""
    from web.backend.queue_manager import _resolve_context_to_track_ids
    from web.backend.schemas import PlayContext
    from unittest.mock import patch

    # Mock session with tracks 1,2,3 unassigned, 4,5 assigned
    mock_session = create_test_session(
        all_track_ids=[1, 2, 3, 4, 5],
        assigned_track_ids=[4, 5]
    )

    context = PlayContext(
        type="organizer",
        playlist_id=1,
        session_id="test-session-123",
        shuffle=False
    )

    with patch("web.backend.queue_manager.get_session_with_data", return_value=mock_session):
        track_ids = _resolve_context_to_track_ids(context, test_db)

    assert track_ids == [1, 2, 3]
    assert 4 not in track_ids
    assert 5 not in track_ids
```

### Test 2: Sequential Loop Restart

```python
def test_organizer_loop_sequential_returns_none_when_exhausted(test_db):
    """Sequential mode should return None when all tracks excluded (signals queue rebuild)."""
    from web.backend.queue_manager import get_next_track
    from web.backend.schemas import PlayContext
    from unittest.mock import patch

    mock_session = create_test_session(
        all_track_ids=[1, 2, 3]
    )

    context = PlayContext(
        type="organizer",
        playlist_id=1,
        session_id="test-session-123",
        shuffle=False
    )

    # All tracks already excluded
    exclusions = [1, 2, 3]

    with patch("web.backend.queue_manager.get_session_with_data", return_value=mock_session):
        next_track = get_next_track(context, exclusions, test_db, shuffle=False)

    # Should return None to signal queue rebuild needed
    assert next_track is None
```

### Test 3: Shuffle Loop Restart

```python
def test_organizer_loop_shuffle_returns_none_when_exhausted(test_db):
    """Shuffle mode should return None when all tracks excluded (signals queue rebuild)."""
    from web.backend.queue_manager import get_next_track
    from web.backend.schemas import PlayContext
    from unittest.mock import patch

    mock_session = create_test_session(
        all_track_ids=[1, 2, 3, 4, 5]
    )

    context = PlayContext(
        type="organizer",
        playlist_id=1,
        session_id="test-session-123",
        shuffle=True
    )

    # All tracks excluded
    exclusions = [1, 2, 3, 4, 5]

    with patch("web.backend.queue_manager.get_session_with_data", return_value=mock_session):
        next_track = get_next_track(context, exclusions, test_db, shuffle=True)

    assert next_track is None
```

### Test 4: Inactive Session Returns Empty

```python
def test_resolve_organizer_context_inactive_session_returns_empty(test_db):
    """Inactive sessions should return empty track list."""
    from web.backend.queue_manager import _resolve_context_to_track_ids
    from web.backend.schemas import PlayContext
    from unittest.mock import patch

    # Session is "applied" (inactive)
    mock_session = create_test_session(
        status="applied",
        all_track_ids=[1, 2, 3]
    )

    context = PlayContext(
        type="organizer",
        playlist_id=1,
        session_id="test-session-123",
        shuffle=False
    )

    with patch("web.backend.queue_manager.get_session_with_data", return_value=mock_session):
        track_ids = _resolve_context_to_track_ids(context, test_db)

    assert track_ids == []
```

## Integration Tests (test_organizer_queue.py)

### Test 5: Queue Update on Assignment

```python
@pytest.mark.asyncio
async def test_queue_update_removes_assigned_track():
    """Assigning a track should remove it from queue in real-time."""
    from web.backend.routers.buckets import _update_organizer_queue_if_active
    from web.backend.routers.player import _playback_state
    from unittest.mock import patch, AsyncMock

    # Setup initial queue with tracks 1,2,3
    _playback_state.queue = [
        {"id": 1, "title": "Track 1"},
        {"id": 2, "title": "Track 2"},
        {"id": 3, "title": "Track 3"}
    ]
    _playback_state.current_track = {"id": 1, "title": "Track 1"}
    _playback_state.queue_index = 0

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

    with patch("web.backend.routers.buckets.get_playback_state", return_value=mock_state), \
         patch("web.backend.routers.buckets.get_session_with_data", return_value=mock_session), \
         patch("web.backend.routers.buckets.sync_manager.broadcast", new_callable=AsyncMock):

        await _update_organizer_queue_if_active("test-session-123")

    # Queue should now only have tracks 1 and 3
    assert len(_playback_state.queue) == 2
    assert _playback_state.queue[0]["id"] == 1
    assert _playback_state.queue[1]["id"] == 3
    assert all(t["id"] != 2 for t in _playback_state.queue)
```

### Test 6: Queue Update on Unassignment

```python
@pytest.mark.asyncio
async def test_queue_update_adds_unassigned_track():
    """Unassigning a track should add it back to queue in real-time."""
    from web.backend.routers.buckets import _update_organizer_queue_if_active
    from web.backend.routers.player import _playback_state
    from unittest.mock import patch, AsyncMock

    # Setup queue missing track 2 (was assigned)
    _playback_state.queue = [
        {"id": 1, "title": "Track 1"},
        {"id": 3, "title": "Track 3"}
    ]

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
        assigned_track_ids=[]  # Track 2 unassigned
    )

    # Mock batch_fetch to return track 2
    mock_tracks = {
        1: {"id": 1, "title": "Track 1"},
        2: {"id": 2, "title": "Track 2"},
        3: {"id": 3, "title": "Track 3"}
    }

    with patch("web.backend.routers.buckets.get_playback_state", return_value=mock_state), \
         patch("web.backend.routers.buckets.get_session_with_data", return_value=mock_session), \
         patch("web.backend.routers.buckets.sync_manager.broadcast", new_callable=AsyncMock):

        # Note: This test needs queue to be rebuilt or track 2 added back
        # The current implementation filters existing queue, doesn't add new tracks
        # This is a potential gap - unassigned tracks won't appear until queue rebuild
        await _update_organizer_queue_if_active("test-session-123")

    # This test will fail with current implementation - tracks don't get added back
    # Queue rebuild is needed, or we need to modify _update_organizer_queue_if_active
    # to fetch and add unassigned tracks
```

### Test 7: Session Validation

```python
def test_play_endpoint_rejects_invalid_organizer_session(client):
    """Play endpoint should validate organizer session exists and is active."""
    from unittest.mock import patch

    # Test missing session
    with patch("web.backend.routers.player.get_session_with_data", return_value=None):
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
    with patch("web.backend.routers.player.get_session_with_data", return_value=mock_session):
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
```

## Verification

Run all tests:
```bash
uv run pytest web/backend/tests/test_queue_manager.py -v
uv run pytest web/backend/tests/test_organizer_queue.py -v
```

Expected results:
- ✅ test_resolve_organizer_context_returns_only_unassigned
- ✅ test_organizer_loop_sequential_returns_none_when_exhausted
- ✅ test_organizer_loop_shuffle_returns_none_when_exhausted
- ✅ test_resolve_organizer_context_inactive_session_returns_empty
- ✅ test_queue_update_removes_assigned_track
- ❓ test_queue_update_adds_unassigned_track (may fail - see note in test)
- ✅ test_play_endpoint_rejects_invalid_organizer_session

## Known Gaps

**Test 6 reveals a potential issue:** The current `_update_organizer_queue_if_active()` implementation only FILTERS the existing queue - it doesn't ADD tracks back when they're unassigned. Unassigned tracks won't appear until the next queue rebuild.

**Options:**
1. Accept this limitation - unassigned tracks appear on next natural queue rebuild
2. Modify `_update_organizer_queue_if_active()` to fetch missing tracks and add them back
3. Trigger a full queue rebuild when tracks are unassigned

This should be discussed and decided before implementation.
