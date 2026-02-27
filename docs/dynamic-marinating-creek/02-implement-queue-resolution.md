---
task: 02-implement-queue-resolution
status: done
depends: [01-extend-playcontext-schema]
files:
  - path: web/backend/queue_manager.py
    action: modify
---

# Implement Queue Resolution for Organizer Context

## Context
Extend the queue manager to handle the new "organizer" context type. This includes resolving unassigned tracks from bucket sessions, supporting shuffle mode, and implementing automatic looping when the queue exhausts.

## Files to Modify/Create
- web/backend/queue_manager.py (modify)

## Implementation Details

### 1. Resolve Context to Track IDs

**Function: `_resolve_context_to_track_ids()` (line 607)**

Add new case after line 670 (after comparison context):

```python
elif context.type == "organizer" and context.session_id:
    # Organizer context - return only unassigned tracks
    from ..queries.buckets import get_session_with_data
    session = get_session_with_data(context.session_id)
    if session and session["status"] == "active":
        return session["unassigned_track_ids"]
    else:
        logger.warning(f"Organizer session {context.session_id} not found or inactive")
        return []
```

### 2. Shuffle Mode Support

**Function: `_get_random_track_from_playlist()` (line 406)**

Add new case after line 441 (after comparison context):

```python
elif context.type == "organizer" and context.session_id:
    # Organizer shuffle mode
    from ..queries.buckets import get_session_with_data
    session = get_session_with_data(context.session_id)
    if session and session["status"] == "active":
        available = [tid for tid in session["unassigned_track_ids"] if tid not in exclusion_ids]
        if not available and session["unassigned_track_ids"]:
            # Loop restart - return None to signal queue rebuild needed
            # Caller (player.py) should detect None and call rebuild_queue()
            logger.info("Organizer loop exhausted - triggering queue rebuild")
            return None
        return random.choice(available) if available else None
    return None
```

### 3. Sequential Loop Support

**Function: `get_next_track()` (line 78)**

Add looping logic for sequential organizer playback. After line 119, modify:

```python
else:
    # Default sequential playback by track_number
    all_track_ids = _resolve_context_to_track_ids(context, db_conn)
    # Filter out exclusions
    available = [tid for tid in all_track_ids if tid not in exclusion_ids]

    # NEW: Loop restart for organizer context
    if not available and all_track_ids and context.type == "organizer":
        # All tracks excluded - return None to signal queue rebuild needed
        # Caller should detect None and call rebuild_queue() to clear exclusions
        logger.info("Organizer loop exhausted - triggering queue rebuild")
        return None

    return available[0] if available else None
```

### 4. Context Reconstruction

**Function: `_reconstruct_play_context()` (line 703)**

Add organizer case after line 735 (after comparison):

**Note:** This implementation assumes task 00 (database-migration) is complete and `context_session_id` is available in the loaded queue state.

```python
elif context_type == "organizer":
    # Reconstruct organizer context with session_id from database
    # (requires context_session_id column added in task 00)
    from ..queries.buckets import get_session_with_data

    # Validate session still exists and is active
    if context_session_id:
        session = get_session_with_data(context_session_id)
        if session and session["status"] == "active":
            return PlayContext(
                type="organizer",
                playlist_id=context_id,
                session_id=context_session_id,
                shuffle=shuffle
            )
        else:
            logger.warning(f"Organizer session {context_session_id} no longer active, falling back to playlist")

    # Fallback to regular playlist if session invalid/missing
    return PlayContext(
        type="playlist",
        playlist_id=context_id,
        shuffle=shuffle
    )
```

## Verification
- Run backend tests: `uv run pytest web/backend/tests/ -k queue`
- Test organizer context resolution returns only unassigned track IDs
- Test shuffle mode with loop restart (returns None when exhausted)
- Test sequential mode with loop restart (returns None when exhausted)
- Verify context reconstruction for organizer type

## Important Note on Loop Restart

When all tracks are excluded, `get_next_track()` returns `None` to signal that the queue needs rebuilding. The caller (typically in `player.py`'s `/next` endpoint) **MUST** detect this and call `rebuild_queue()` to clear exclusions and restart the loop with a fresh queue.

**Critical pattern for `/next` endpoint:**
```python
next_track_id = get_next_track(context, exclusions, db_conn, shuffle)

if next_track_id is None and context.type == "organizer":
    # Loop exhausted - rebuild queue to restart
    logger.info("Organizer queue exhausted, rebuilding for loop restart")
    new_queue = rebuild_queue(context, current_track_id, queue, queue_index, db_conn, shuffle)
    _playback_state.queue = new_queue
    _playback_state.queue_index = 0
    next_track_id = new_queue[0] if new_queue else None
```

This approach properly clears the queue's exclusion state rather than just locally bypassing it. The None return is an explicit signal that requires action from the caller.
