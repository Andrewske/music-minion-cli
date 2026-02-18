---
task: 03-backend-player-integration
status: pending
depends: [02-queue-manager-module]
files:
  - path: web/backend/routers/player.py
    action: modify
---

# Backend Player Integration - API Updates

## Context
Integrate the queue_manager module into the player router. Update existing endpoints to use the rolling window, add new endpoints for smooth shuffle toggle and manual sort, and implement startup recovery.

## Files to Modify/Create
- web/backend/routers/player.py (modify)

## Implementation Details

### Import queue_manager

Add at top of file:
```python
from ..queue_manager import (
    initialize_queue,
    get_next_track,
    rebuild_queue,
    save_queue_state,
    load_queue_state,
)
```

### Update _playback_state

Add new fields to the global `_playback_state` object:
```python
_playback_state.shuffle_enabled = True  # Default shuffle on
_playback_state.sort_spec = None  # dict with 'field' and 'direction'
```

### Modified Endpoints

#### POST /player/play

**Changes:**
1. Replace `resolve_queue()` call with `initialize_queue()`
2. Increase queue size from 50 → 100 tracks
3. Add shuffle and sort state to `_playback_state`
4. Call `save_queue_state()` after setting queue

**Code:**
```python
@router.post("/play")
async def play(request: PlayRequest, db=Depends(get_db)):
    # 1. Initialize queue using queue_manager (not resolve_queue)
    queue_ids = initialize_queue(
        context=request.context,
        db_conn=db,
        window_size=100,  # Changed from 50
        shuffle=request.context.shuffle if hasattr(request.context, 'shuffle') else True,
        sort_spec=None
    )

    # 2. Fetch full track metadata
    queue_tracks = batch_fetch_tracks_with_metadata(queue_ids, db, preserve_order=True)

    # 3. Find requested track in queue
    queue_index = 0
    for i, track in enumerate(queue_tracks):
        if track["id"] == request.track_id:
            queue_index = i
            break

    # 4. Update global state
    _playback_state.current_track = queue_tracks[queue_index]
    _playback_state.queue = queue_tracks
    _playback_state.queue_index = queue_index
    _playback_state.position_ms = 0
    _playback_state.track_started_at = time.time()
    _playback_state.is_playing = True
    _playback_state.current_context = request.context
    _playback_state.shuffle_enabled = request.context.shuffle if hasattr(request.context, 'shuffle') else True
    _playback_state.sort_spec = None

    # 5. Persist queue state
    save_queue_state(
        context=request.context,
        queue_ids=queue_ids,
        queue_index=queue_index,
        shuffle=_playback_state.shuffle_enabled,
        sort_spec=None,
        db_conn=db
    )

    # 6. Broadcast to all devices
    await sync_manager.broadcast("playback:state", get_playback_state())

    return {"status": "playing"}
```

#### POST /player/next

**Changes:**
1. After advancing index, check lookahead buffer
2. If buffer < 50, pull 1 new track via `get_next_track()`
3. Append to queue and save state

**Code:**
```python
@router.post("/next")
async def next_track(db=Depends(get_db)):
    global _playback_state

    # Advance queue index
    _playback_state.queue_index += 1

    if _playback_state.queue_index >= len(_playback_state.queue):
        # End of queue
        _playback_state.is_playing = False
        _playback_state.current_track = None
    else:
        # Update current track
        _playback_state.current_track = _playback_state.queue[_playback_state.queue_index]
        _playback_state.position_ms = 0
        _playback_state.track_started_at = time.time()

        # NEW: Check lookahead buffer and refill
        tracks_ahead = len(_playback_state.queue) - _playback_state.queue_index

        if tracks_ahead < 50:  # Lookahead threshold
            # Build exclusion list: all tracks ahead + current
            exclusion_ids = [
                t["id"] for t in _playback_state.queue[_playback_state.queue_index:]
            ]

            # Pull 1 new track
            new_track_id = get_next_track(
                context=_playback_state.current_context,
                exclusion_ids=exclusion_ids,
                db_conn=db,
                shuffle=_playback_state.shuffle_enabled,
                sort_spec=_playback_state.sort_spec
            )

            if new_track_id:
                # Fetch full metadata
                new_tracks = batch_fetch_tracks_with_metadata([new_track_id], db)
                _playback_state.queue.append(new_tracks[0])

                # Save updated state
                queue_ids = [t["id"] for t in _playback_state.queue]
                save_queue_state(
                    context=_playback_state.current_context,
                    queue_ids=queue_ids,
                    queue_index=_playback_state.queue_index,
                    shuffle=_playback_state.shuffle_enabled,
                    sort_spec=_playback_state.sort_spec,
                    db_conn=db
                )

    # Broadcast updated state
    await sync_manager.broadcast("playback:state", get_playback_state())

    return {"status": "next"}
```

### New Endpoints

#### POST /player/toggle-shuffle

```python
@router.post("/toggle-shuffle")
async def toggle_shuffle(db=Depends(get_db)):
    """Toggle shuffle without interrupting playback."""
    global _playback_state

    if not _playback_state.current_track:
        raise HTTPException(400, "No active playback")

    # Toggle shuffle state
    new_shuffle = not _playback_state.shuffle_enabled
    _playback_state.shuffle_enabled = new_shuffle

    # Clear sort spec if enabling shuffle
    sort_spec = None if new_shuffle else _playback_state.sort_spec

    # Rebuild queue preserving current track
    queue_ids = [t["id"] for t in _playback_state.queue]
    new_queue_ids = rebuild_queue(
        context=_playback_state.current_context,
        current_track_id=_playback_state.current_track["id"],
        queue=queue_ids,
        queue_index=_playback_state.queue_index,
        db_conn=db,
        shuffle=new_shuffle,
        sort_spec=sort_spec
    )

    # Fetch full track metadata
    new_queue = batch_fetch_tracks_with_metadata(new_queue_ids, db, preserve_order=True)

    _playback_state.queue = new_queue
    _playback_state.sort_spec = sort_spec

    # Persist state
    save_queue_state(
        context=_playback_state.current_context,
        queue_ids=new_queue_ids,
        queue_index=_playback_state.queue_index,
        shuffle=new_shuffle,
        sort_spec=sort_spec,
        db_conn=db
    )

    # Broadcast
    await sync_manager.broadcast("playback:state", get_playback_state())

    return {
        "shuffle_enabled": new_shuffle,
        "queue_size": len(new_queue)
    }
```

#### POST /player/set-sort

```python
class SetSortRequest(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
    field: str  # 'title', 'artist', 'bpm', 'year', 'elo_rating'
    direction: Literal["asc", "desc"]

@router.post("/set-sort")
async def set_sort(request: SetSortRequest, db=Depends(get_db)):
    """Apply manual table sort (disables shuffle)."""
    global _playback_state

    if not _playback_state.current_track:
        raise HTTPException(400, "No active playback")

    sort_spec = {"field": request.field, "direction": request.direction}

    # Disable shuffle
    _playback_state.shuffle_enabled = False
    _playback_state.sort_spec = sort_spec

    # Rebuild queue with new sort
    queue_ids = [t["id"] for t in _playback_state.queue]
    new_queue_ids = rebuild_queue(
        context=_playback_state.current_context,
        current_track_id=_playback_state.current_track["id"],
        queue=queue_ids,
        queue_index=_playback_state.queue_index,
        db_conn=db,
        shuffle=False,
        sort_spec=sort_spec
    )

    new_queue = batch_fetch_tracks_with_metadata(new_queue_ids, db, preserve_order=True)

    _playback_state.queue = new_queue

    # Persist state
    save_queue_state(
        context=_playback_state.current_context,
        queue_ids=new_queue_ids,
        queue_index=_playback_state.queue_index,
        shuffle=False,
        sort_spec=sort_spec,
        db_conn=db
    )

    # Broadcast
    await sync_manager.broadcast("playback:state", get_playback_state())

    return {
        "queue_size": len(new_queue),
        "sort": sort_spec
    }
```

### Startup Recovery

Add startup event handler to restore queue state:

```python
@router.on_event("startup")
async def restore_queue_state():
    """Restore queue state on server restart."""
    global _playback_state

    try:
        with get_db() as db:
            state = load_queue_state(db)

            if state:
                logger.info(f"Restoring queue state: {len(state['queue_ids'])} tracks")

                # Fetch full track metadata
                queue_tracks = batch_fetch_tracks_with_metadata(
                    state["queue_ids"], db, preserve_order=True
                )

                # Restore state
                _playback_state.queue = queue_tracks
                _playback_state.queue_index = state["queue_index"]
                _playback_state.shuffle_enabled = state["shuffle_enabled"]
                _playback_state.sort_spec = state.get("sort_spec")
                _playback_state.current_context = state["context"]

                if state["queue_index"] < len(queue_tracks):
                    _playback_state.current_track = queue_tracks[state["queue_index"]]

                # Don't auto-resume playback (user must manually press play)
                _playback_state.is_playing = False

                logger.info("Queue state restored successfully")
    except Exception as e:
        logger.exception("Failed to restore queue state")
```

### Update get_playback_state()

Add sort_spec to the state response:

```python
def get_playback_state() -> dict:
    return {
        # ... existing fields ...
        "shuffleEnabled": _playback_state.shuffle_enabled,
        "sortSpec": _playback_state.sort_spec,  # NEW
    }
```

## Verification

```bash
# Start server in web mode
uv run music-minion --web

# Test in browser console (http://localhost:5173):

# 1. Play a playlist
# Check network tab: POST /api/player/play
# Verify queue has ~100 tracks in response

# 2. Skip through 60 tracks
# Check logs: Queue should grow dynamically
tail -f music-minion-uvicorn.log

# 3. Toggle shuffle
fetch('http://localhost:8642/api/player/toggle-shuffle', {method: 'POST'})
# Verify current track unchanged, queue rebuilt

# 4. Set manual sort
fetch('http://localhost:8642/api/player/set-sort', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({field: 'bpm', direction: 'asc'})
})
# Verify shuffle disabled, queue sorted

# 5. Restart server
# Ctrl+C, then restart
# Check /api/player/state - queue should be restored
```

**Expected behavior:**
- Initial queue has 100 tracks
- Lookahead buffer maintains 50+ tracks ahead of current position
- Shuffle toggle rebuilds queue without audio interruption
- Manual sort disables shuffle and reorders queue
- Server restart preserves queue state
