---
task: 02-migrate-player-router
status: pending
depends: [01-create-player-state-module]
files:
  - path: web/backend/routers/player.py
    action: modify
---

# Migrate Player Router to Immutable State

## Context
The player router has ~15 mutation sites that directly modify `_playback_state`. This task converts all mutations to use the new `update_state()` pattern.

## Files to Modify/Create
- web/backend/routers/player.py (modify)

## Implementation Details

### Remove from player.py:
- `PlaybackState` class definition (lines 58-76)
- `_playback_state = PlaybackState()` (line 79)
- All `global _playback_state` declarations

### Keep in player.py:
- `_next_lock` (line 82) - still needed for operation-level atomicity (DB ops must be ordered)

**Note on locks**: Two locks serve different purposes:
- `_next_lock`: Coarse lock for business logic atomicity (history entries, queue persistence)
- `_state_lock` (inside `update_state()`): Fine lock for state mutation atomicity

### Add imports:
```python
from ..player_state import get_state, get_state_dict, update_state, PlaybackState
```

### Update `get_playback_state()`:
```python
def get_playback_state() -> dict:
    """Get current playback state with server time for clock sync."""
    state_dict = get_state_dict()
    state_dict["sortSpec"] = get_state().sort_spec
    return state_dict
```

### Convert mutation sites:

**`play()` endpoint (lines 221-233):**
```python
await update_state({
    "current_track": queue_tracks[queue_index],
    "queue": tuple(queue_tracks),
    "queue_index": queue_index,
    "position_ms": 0,
    "track_started_at": now,
    "is_playing": True,
    "active_device_id": active_device_id,
    "current_context": request.context.model_dump(),
    "shuffle_enabled": request.context.shuffle if hasattr(request.context, 'shuffle') else True,
    "sort_spec": None,
    "position_in_playlist": 0,
    "duration_ms": 0,
    "current_history_id": history_id
})
```

**`pause()` endpoint (lines 274-281):**
```python
state = get_state()
elapsed_ms = 0
if state.track_started_at:
    elapsed_ms = int((time.time() - state.track_started_at) * 1000)

await update_state({
    "duration_ms": state.duration_ms + elapsed_ms,
    "position_ms": state.position_ms + elapsed_ms,
    "is_playing": False,
    "track_started_at": None
})
```

**`resume()` endpoint (lines 301-303):**
```python
await update_state({
    "is_playing": True,
    "track_started_at": time.time()
})
```

**`next_track()` endpoint - keep _next_lock, use update_state inside:**
```python
async def next_track(reason: str = "skip", db=Depends(get_db)):
    async with _next_lock:  # Keep for operation atomicity
        state = get_state()  # Immutable snapshot

    # ... history cleanup logic ...

    def advance_queue(s: PlaybackState) -> PlaybackState:
        new_index = s.queue_index + 1
        if new_index >= len(s.queue):
            return s.model_copy(update={
                "is_playing": False,
                "current_track": None,
                "current_history_id": None
            })
        return s.model_copy(update={
            "queue_index": new_index,
            "current_track": s.queue[new_index],
            "position_ms": 0,
            "track_started_at": time.time(),
            "duration_ms": 0
        })

    await update_state(advance_queue)
```

**`prev_track()` endpoint (lines 457-465):**
```python
state = get_state()
if state.position_ms > 3000:
    await update_state({
        "position_ms": 0,
        "track_started_at": time.time() if state.is_playing else None
    })
else:
    new_index = max(0, state.queue_index - 1)
    await update_state({
        "queue_index": new_index,
        "current_track": state.queue[new_index],
        "position_ms": 0,
        "track_started_at": time.time() if state.is_playing else None
    })
```

**`seek()` endpoint (lines 483-489):**
```python
state = get_state()
elapsed_ms = 0
if state.track_started_at:
    elapsed_ms = int((time.time() - state.track_started_at) * 1000)

await update_state({
    "duration_ms": state.duration_ms + elapsed_ms,
    "position_ms": request.position_ms,
    "track_started_at": time.time() if state.is_playing else None
})
```

**`toggle_shuffle()` and `set_sort()` - similar pattern**

**`get_devices()` endpoint:**
```python
@router.get("/devices")
async def get_devices():
    """List connected devices."""
    from ..sync_manager import sync_manager

    devices = [
        {
            "id": device_id,
            "name": device_info["name"],
            "connected_at": device_info["connected_at"],
            "is_active": device_id == get_state().active_device_id,
        }
        for device_id, device_info in sync_manager.devices.items()
    ]

    return devices
```

**`restore_player_queue_state()` - startup restoration:**
```python
async def restore_player_queue_state():
    """Restore queue state from database. Called by main app startup handler."""
    from music_minion.core.database import get_db_connection
    from ..queries.tracks import batch_fetch_tracks_with_metadata

    try:
        with get_db_connection() as db:
            state = load_queue_state(db)

            if not state:
                logger.info("No saved queue state found")
                return

            # ... validation logic (unchanged) ...

            logger.info(f"Restoring queue state: {len(state['queue_ids'])} tracks")

            queue_tracks = batch_fetch_tracks_with_metadata(
                state["queue_ids"], db, preserve_order=True
            )

            if not queue_tracks:
                logger.warning("No tracks found for saved queue IDs")
                return

            # Single atomic update instead of multiple mutations
            current_track = None
            if state["queue_index"] < len(queue_tracks):
                current_track = queue_tracks[state["queue_index"]]

            await update_state({
                "queue": tuple(queue_tracks),
                "queue_index": state["queue_index"],
                "shuffle_enabled": state["shuffle_enabled"],
                "sort_spec": state.get("sort_spec"),
                "position_in_playlist": state.get("position_in_playlist", 0),
                "current_context": state["context"],
                "current_track": current_track,
                "is_playing": False,  # Don't auto-resume
            }, broadcast=False)  # No clients connected at startup

            logger.info("Queue state restored successfully")
    except Exception:
        logger.exception("Failed to restore queue state, starting with clean state")
```

**`update_organizer_queue()` - use callable:**
```python
async def update_organizer_queue(session_id: str) -> None:
    state = get_state()
    # ... validation logic ...

    def update_queue(s: PlaybackState) -> PlaybackState:
        # Filter and update queue
        updated_queue = tuple(t for t in s.queue if t["id"] in new_unassigned_set)
        # ... add newly unassigned ...
        new_index = next((i for i, t in enumerate(updated_queue) if t["id"] == current_track_id), 0)
        return s.model_copy(update={
            "queue": updated_queue,
            "queue_index": new_index
        })

    await update_state(update_queue)
```

### Queue tuple patterns:
```python
# Append to queue
new_queue = state.queue + (new_track,)

# Filter queue
new_queue = tuple(t for t in state.queue if condition)

# Extend queue
new_queue = state.queue + tuple(new_tracks)
```

## Verification

```bash
# Run existing player tests
uv run pytest web/backend/tests/ -k player -v

# Manual test: start web mode and verify play/pause/skip work
music-minion --web
```
