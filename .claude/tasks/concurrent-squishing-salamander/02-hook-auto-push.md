---
task: 02-hook-auto-push
status: done
depends: [01-sc-push-worker]
files:
  - path: web/backend/queries/buckets.py
    action: modify
---

# Hook Auto-Push into Bucket Sync Functions

## Context
The bucket sync functions (`sync_track_to_linked_playlist`, `unsync_track_from_linked_playlist`, `sync_existing_bucket_tracks_to_playlist`) currently only write to the local SQLite database. We need to enqueue SC push tasks after each local sync operation so changes propagate to SoundCloud automatically.

## Files to Modify
- `web/backend/queries/buckets.py` (modify)

## Implementation Details

**3 one-line additions + 1 import block.**

### Import (top of file)
```python
from web.backend.sc_push_worker import (
    enqueue_sc_push_add,
    enqueue_sc_push_remove,
    enqueue_sc_push_bulk_sync,
)
```

### `sync_track_to_linked_playlist()` (~line 1112, after commit+log)
Add after the existing `logger.info(...)`:
```python
enqueue_sc_push_add(playlist_id, track_id)
```

### `unsync_track_from_linked_playlist()` (~line 1155, after commit+log)
Add after the existing `logger.info(...)`:
```python
enqueue_sc_push_remove(playlist_id, track_id)
```

### `sync_existing_bucket_tracks_to_playlist()` (~line 1047, after commit+log)
Add after the existing `logger.info(...)`:
```python
enqueue_sc_push_bulk_sync(playlist_id)
```

## Verification
1. Start web mode, ensure SC authenticated
2. Link a bucket to a SC-linked playlist → check logs for `SC push: synced N tracks` (bulk sync)
3. Assign a track with `soundcloud_id` to a linked bucket → check logs for single track push
4. Assign a local-only track (no `soundcloud_id`) → should silently skip in worker
5. Unassign a track → check logs for removal push
