---
task: 05-player-organizer-support
status: pending
depends: [02-implement-queue-resolution]
files:
  - path: web/backend/routers/player.py
    action: modify
---

# Player Organizer Support: Validation + Loop Handling

## Context
Two related changes to player.py for organizer context support:
1. **Validation**: Ensure organizer contexts reference valid, active bucket sessions
2. **Loop Handling**: Detect queue exhaustion and rebuild for continuous looping

**Note:** Basic validation (session_id required for organizer) is handled by Pydantic validator in PlayContext schema (task 01). This task adds runtime validation and loop restart logic.

## Files to Modify/Create
- web/backend/routers/player.py (modify)

## Implementation Details

### 1. Session Validation in `/play` Endpoint

**In the `play()` endpoint** - Add session validation after parsing request:

```python
# Validate organizer session exists and is active
if request.context.type == "organizer":
    from ..queries.buckets import get_session_with_data
    session = get_session_with_data(request.context.session_id)
    if not session:
        raise HTTPException(404, f"Organizer session {request.context.session_id} not found")
    if session["status"] != "active":
        raise HTTPException(400, f"Organizer session is {session['status']}, cannot play")
```

### 2. Loop Restart in `/next` Endpoint

**In the `next_track()` endpoint** - After `get_next_track()` returns None, check if organizer context needs loop restart.

Find the existing code block (around line 370-384):
```python
new_track_id = get_next_track(
    context=_playback_state.current_context,
    exclusion_ids=exclusion_ids,
    ...
)

if new_track_id:
    # Fetch full metadata
    ...
```

Replace with:
```python
new_track_id = get_next_track(
    context=_playback_state.current_context,
    exclusion_ids=exclusion_ids,
    ...
)

# Handle organizer loop restart
if new_track_id is None and _playback_state.current_context.type == "organizer":
    # Queue exhausted - rebuild for loop restart
    logger.info("Organizer queue exhausted, rebuilding for loop restart")
    from ..queue_manager import rebuild_queue

    new_queue_ids = rebuild_queue(
        context=_playback_state.current_context,
        current_track_id=_playback_state.current_track["id"],
        queue=[t["id"] for t in _playback_state.queue],
        queue_index=_playback_state.queue_index,
        db_conn=db,
        shuffle=_playback_state.shuffle_enabled,
        sort_spec=_playback_state.sort_spec
    )

    if new_queue_ids:
        # Fetch metadata for new queue
        new_tracks = batch_fetch_tracks_with_metadata(new_queue_ids, db)
        _playback_state.queue = new_tracks
        _playback_state.queue_index = 0
        _playback_state.current_track = new_tracks[0]
        _playback_state.position_ms = 0
        _playback_state.track_started_at = time.time()

        # Start history entry for first track of new loop
        from music_minion.domain.radio.history import start_play
        history_id = start_play(
            track_id=_playback_state.current_track["id"],
            source_type="local"
        )
        _playback_state.current_history_id = history_id

        # Save state
        save_queue_state(
            context=_playback_state.current_context,
            queue_ids=new_queue_ids,
            queue_index=0,
            shuffle=_playback_state.shuffle_enabled,
            sort_spec=_playback_state.sort_spec,
            db_conn=db
        )

elif new_track_id:
    # Normal case: append new track to queue
    new_tracks = batch_fetch_tracks_with_metadata([new_track_id], db)
    if new_tracks:
        _playback_state.queue.append(new_tracks[0])
        # ... rest of existing logic
```

## Verification

### Session Validation
- Test missing session_id: `POST /api/player/play` with `context.type: "organizer"` but no `session_id`
  - Expect: 400 Bad Request
- Test invalid session_id: Use non-existent session UUID
  - Expect: 404 Not Found
- Test inactive session: Apply a session, then try to play from it
  - Expect: 400 Bad Request with message about session status
- Test valid session: Create active session and play
  - Expect: 200 OK, playback starts

### Loop Restart
- Play through all unassigned tracks in organizer mode
- When queue exhausts, verify:
  - Logger shows "Organizer queue exhausted, rebuilding for loop restart"
  - Queue rebuilds with fresh track list
  - Playback continues from first track of new loop
  - Shuffle mode: new random order on each loop
  - Sequential mode: same order on each loop
