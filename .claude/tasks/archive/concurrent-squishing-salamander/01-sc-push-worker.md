---
task: 01-sc-push-worker
status: done
depends: []
files:
  - path: web/backend/sc_push_worker.py
    action: create
---

# Background SoundCloud Push Worker

## Context
When tracks are assigned to a bucket linked to a SoundCloud-backed playlist, we need to push those changes to SoundCloud. This worker provides a fire-and-forget queue that processes SC API calls in a background daemon thread, keeping bucket assignment fast (local DB only) while SC sync happens asynchronously.

## Files to Create
- `web/backend/sc_push_worker.py` (new, ~90 lines)

## Implementation Details

### Task types (NamedTuple)
- `SCPushAdd(playlist_id: int, track_id: int)` — single track add
- `SCPushRemove(playlist_id: int, track_id: int)` — single track remove
- `SCPushBulkSync(playlist_id: int)` — full playlist sync on link

### Public API (3 enqueue functions)
- `enqueue_sc_push_add(playlist_id, track_id)`
- `enqueue_sc_push_remove(playlist_id, track_id)`
- `enqueue_sc_push_bulk_sync(playlist_id)`

Each lazily starts the daemon thread on first call via `_ensure_worker()`.

### Module-level state
```python
_queue: queue.Queue = queue.Queue()
_worker_thread: threading.Thread | None = None
_worker_lock = threading.Lock()
```

### Worker thread function
- `threading.current_thread().silent_logging = True` (per CLAUDE.md background thread pattern)
- Infinite loop: `task = _queue.get()`, process, `_queue.task_done()`
- Entire loop body wrapped in try/except to prevent thread death

### Handler: `_handle_add(playlist_id, track_id)`
1. Query DB: `SELECT soundcloud_id FROM tracks WHERE id = ?` — skip if None
2. Query DB: `SELECT soundcloud_playlist_id FROM playlists WHERE id = ?` — skip if None
3. `get_web_provider_state()` — skip if None (not authenticated)
4. Call `add_track_to_playlist(state, sc_playlist_id, sc_track_id)`
5. Log success/failure

### Handler: `_handle_remove(playlist_id, track_id)`
Same pattern as add, calls `remove_track_from_playlist`.

### Handler: `_handle_bulk_sync(playlist_id)`
Reuse pattern from `sync_playlist_to_soundcloud` endpoint (`routers/playlists.py:560-654`):
1. Get `soundcloud_playlist_id` for playlist — skip if None
2. Query ALL tracks in playlist with `soundcloud_id IS NOT NULL`, ordered by position
3. Get auth state — skip if None
4. Call `reorder_playlist(state, sc_playlist_id, sc_track_ids)` — single PUT, idempotent

### Thread details
- Daemon thread — dies with process, no cleanup needed
- Single thread serializes all SC mutations (avoids GET→PUT race conditions on same playlist)

### Error handling
Log-only via loguru. Auth failures, network errors, rate limits all logged and skipped. No retry queue.

### Key imports
```python
from music_minion.core.database import get_db_connection
from web.backend.soundcloud_auth import get_web_provider_state
from music_minion.domain.library.providers.soundcloud.api import (
    add_track_to_playlist,
    remove_track_from_playlist,
    reorder_playlist,
)
```

## Verification
- Import the module: `from web.backend.sc_push_worker import enqueue_sc_push_add`
- Call `enqueue_sc_push_add(playlist_id, track_id)` with a known SC-linked playlist
- Check logs for SC push messages
- Call with a non-SC playlist → verify silent skip
