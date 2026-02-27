---
task: 03-real-time-queue-updates
status: pending
depends: [02-implement-queue-resolution]
files:
  - path: web/backend/routers/buckets.py
    action: modify
---

# Implement Real-Time Queue Updates

## Context
When tracks are assigned to or unassigned from buckets, the playback queue needs to update in real-time. This task adds a helper function that filters the queue and broadcasts updates via WebSocket to all connected devices.

## Files to Modify/Create
- web/backend/routers/buckets.py (modify)

## Implementation Details

### 1. Add Queue Update Helper Function

**After line 100** (end of `create_or_resume_session`), add new helper function:

```python
async def _update_organizer_queue_if_active(session_id: str) -> None:
    """Update playback queue if currently playing from this organizer session.

    Removes assigned tracks from queue and broadcasts updated state.
    Thread-safe via _next_lock to prevent race conditions with queue polling.
    """
    from .player import get_playback_state, _playback_state, _next_lock
    from ..queries.buckets import get_session_with_data
    from ..sync_manager import sync_manager

    # Get current state (no lock needed for read)
    state = get_playback_state()

    # Only update if currently playing from this organizer session
    if (
        not state
        or not state.get("context")
        or state["context"].get("type") != "organizer"
        or state["context"].get("session_id") != session_id
    ):
        return

    # Fetch updated unassigned tracks
    session = get_session_with_data(session_id)
    if not session or session["status"] != "active":
        return

    # Use set for O(n) lookups instead of O(n*m)
    new_unassigned_set = set(session["unassigned_track_ids"])

    # Acquire lock before modifying queue state
    async with _next_lock:
        # Re-fetch state inside lock to ensure consistency
        current_queue = _playback_state.queue
        current_track_id = _playback_state.current_track.get("id") if _playback_state.current_track else None

        # Filter queue to only include unassigned tracks
        updated_queue = [track for track in current_queue if track["id"] in new_unassigned_set]

        # Detect newly unassigned tracks (not currently in queue) and append them
        current_queue_ids = {t["id"] for t in current_queue}
        newly_unassigned_ids = [tid for tid in new_unassigned_set if tid not in current_queue_ids]

        if newly_unassigned_ids:
            from ..queries.tracks import batch_fetch_tracks_with_metadata
            from ..core.database import get_db_connection
            with get_db_connection() as db_conn:
                newly_unassigned_tracks = batch_fetch_tracks_with_metadata(newly_unassigned_ids, db_conn)
                updated_queue.extend(newly_unassigned_tracks)

        # Recalculate queue index to maintain current track position
        if current_track_id:
            try:
                # Find current track in filtered queue
                new_index = next(i for i, t in enumerate(updated_queue) if t["id"] == current_track_id)
                _playback_state.queue_index = new_index
            except StopIteration:
                # Current track was removed (assigned to bucket)
                # Let it finish naturally, next track will be first in new queue
                _playback_state.queue_index = 0
                logger.info(f"Current track {current_track_id} assigned - will finish then skip to next unassigned")

        # Update queue
        _playback_state.queue = updated_queue

    # Broadcast updated state (outside lock to avoid blocking)
    await sync_manager.broadcast("playback:state", get_playback_state())
    logger.info(f"Updated organizer queue: {len(updated_queue)} unassigned tracks remaining")
```

### 2. Hook Into Assignment Endpoints

**Modify existing endpoints** to call the helper:

Find the `assign_track` endpoint and add after successful assignment:
```python
await _update_organizer_queue_if_active(session_id)
```

Find the `unassign_track` endpoint and add after successful unassignment:
```python
await _update_organizer_queue_if_active(session_id)
```

### 3. Add Bulk Unassign Endpoint (Optional Enhancement)

**Useful for**: Quickly pivoting bucket concepts during organizing ("this bucket isn't working, start over")

Add new endpoint after `unassign_track`:

```python
@router.delete("/sessions/{session_id}/buckets/{bucket_id}/tracks")
async def bulk_unassign_from_bucket(
    session_id: str,
    bucket_id: str,
    db_conn=Depends(get_db)
) -> dict:
    """Unassign all tracks from a bucket (empty the bucket)."""
    from ..queries.buckets import get_session_with_data

    # Validate session exists and is active
    session = get_session_with_data(session_id)
    if not session:
        raise HTTPException(404, f"Session {session_id} not found")
    if session["status"] != "active":
        raise HTTPException(400, f"Session is {session['status']}, cannot modify")

    # Validate bucket exists in session
    bucket = next((b for b in session["buckets"] if b["id"] == bucket_id), None)
    if not bucket:
        raise HTTPException(404, f"Bucket {bucket_id} not found in session")

    # Delete all assignments for this bucket
    cursor = db_conn.execute(
        "DELETE FROM bucket_track_assignments WHERE bucket_id = ?",
        (bucket_id,)
    )
    deleted_count = cursor.rowcount
    db_conn.commit()

    # Update queue if currently playing from this session
    await _update_organizer_queue_if_active(session_id)

    return {
        "session_id": session_id,
        "bucket_id": bucket_id,
        "tracks_unassigned": deleted_count
    }
```

Frontend can add a "Clear Bucket" button that calls:
```
DELETE /api/buckets/{sessionId}/buckets/{bucketId}/tracks
```

## Important Notes

### Thread Safety
The function uses the queue lock from `player.py` to prevent race conditions.

**Required change in web/backend/routers/player.py:**

Change the private lock to a documented public export:

```python
# Replace:
_next_lock = Lock()

# With:
queue_lock = Lock()  # Public export - protects queue state modifications
"""Lock for thread-safe queue operations.

MUST be acquired before modifying:
- _playback_state.queue
- _playback_state.queue_index

Used by:
- /next endpoint (prevents race conditions during track advancement)
- Real-time queue updates (bucket assignment/unassignment)
"""
```

Then update all uses of `_next_lock` to `queue_lock` in player.py, and import as:
```python
from .player import queue_lock
```

### Circular Import Prevention
This function is in `routers/buckets.py` and imports from `routers/player.py`. To avoid circular imports, ensure player.py doesn't directly import from buckets.py. The current architecture should be safe since player.py only imports from `queue_manager.py` and `queries/buckets.py`.

## Verification
- Start organizer session and play a track
- Assign track to bucket via API: `POST /api/buckets/{session_id}/buckets/{bucket_id}/tracks`
- Verify queue updates in real-time (check WebSocket messages)
- Verify assigned track removed from queue
- Unassign a track via API: `DELETE /api/buckets/{session_id}/buckets/{bucket_id}/tracks/{track_id}`
- Verify track reappears in queue immediately
- Verify queue index stays correct after filtering
