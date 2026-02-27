---
task: 03-real-time-queue-updates
status: pending
depends: [02-implement-queue-resolution]
files:
  - path: web/backend/routers/player.py
    action: modify
  - path: web/backend/routers/buckets.py
    action: modify
---

# Implement Real-Time Queue Updates

## Context
When tracks are assigned to or unassigned from buckets, the playback queue needs to update in real-time. This task adds an encapsulated function in player.py (keeps state mutation local) that buckets.py calls via import.

## Files to Modify/Create
- web/backend/routers/player.py (modify) - Add queue update function
- web/backend/routers/buckets.py (modify) - Call the function from endpoints

## Implementation Details

### 1. Add Queue Update Function in player.py

**In player.py**, add after `get_playback_state()` function:

```python
async def update_organizer_queue(session_id: str) -> None:
    """Update playback queue if currently playing from this organizer session.

    Removes assigned tracks from queue, adds unassigned tracks back,
    and broadcasts updated state via WebSocket.

    Called by buckets.py when tracks are assigned/unassigned.
    State mutation stays encapsulated in player.py.
    """
    global _playback_state

    from ..queries.buckets import get_session_with_data
    from ..queries.tracks import batch_fetch_tracks_with_metadata
    from ..sync_manager import sync_manager
    from music_minion.core.database import get_db_connection

    # Check if currently playing from this organizer session
    state = get_playback_state()
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

    new_unassigned_set = set(session["unassigned_track_ids"])

    async with _next_lock:
        current_queue = _playback_state.queue
        current_track_id = _playback_state.current_track.get("id") if _playback_state.current_track else None

        # Filter queue to only include unassigned tracks
        updated_queue = [track for track in current_queue if track["id"] in new_unassigned_set]

        # Detect newly unassigned tracks and append them
        current_queue_ids = {t["id"] for t in current_queue}
        newly_unassigned_ids = [tid for tid in new_unassigned_set if tid not in current_queue_ids]

        if newly_unassigned_ids:
            with get_db_connection() as db_conn:
                newly_unassigned_tracks = batch_fetch_tracks_with_metadata(newly_unassigned_ids, db_conn)
                updated_queue.extend(newly_unassigned_tracks)

        # Recalculate queue index
        if current_track_id:
            try:
                new_index = next(i for i, t in enumerate(updated_queue) if t["id"] == current_track_id)
                _playback_state.queue_index = new_index
            except StopIteration:
                _playback_state.queue_index = 0
                logger.info(f"Current track {current_track_id} assigned - will finish then skip to next unassigned")

        _playback_state.queue = updated_queue

    await sync_manager.broadcast("playback:state", get_playback_state())
    logger.info(f"Updated organizer queue: {len(updated_queue)} unassigned tracks remaining")
```

### 2. Hook Into Assignment Endpoints in buckets.py

**In buckets.py**, import and call the player function:

At top of file, add import:
```python
from .player import update_organizer_queue
```

Find the `assign_track` endpoint and add after successful assignment:
```python
await update_organizer_queue(session_id)
```

Find the `unassign_track` endpoint and add after successful unassignment:
```python
await update_organizer_queue(session_id)
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
    await update_organizer_queue(session_id)

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

## Design Notes

### Encapsulation
State mutation stays in player.py. The `update_organizer_queue()` function encapsulates all state access, so buckets.py only needs to call the function without knowing about `_playback_state` or locks.

### Circular Import Prevention
buckets.py imports from player.py (one-way). player.py imports from queries/buckets.py (not routers/buckets.py). This avoids circular imports.

## Verification
- Start organizer session and play a track
- Assign track to bucket via API: `POST /api/buckets/{session_id}/buckets/{bucket_id}/tracks`
- Verify queue updates in real-time (check WebSocket messages)
- Verify assigned track removed from queue
- Unassign a track via API: `DELETE /api/buckets/{session_id}/buckets/{bucket_id}/tracks/{track_id}`
- Verify track reappears in queue immediately
- Verify queue index stays correct after filtering
