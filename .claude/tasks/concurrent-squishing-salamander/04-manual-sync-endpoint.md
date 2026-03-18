---
task: 04-manual-sync-endpoint
status: done
depends: [03-surface-sc-id]
files:
  - path: web/backend/routers/buckets.py
    action: modify
---

# Manual Bidirectional Sync Endpoint

## Context
The auto-push worker handles fire-and-forget pushes on assignment. This endpoint provides a user-triggered bidirectional sync: pull new tracks from SC into the local playlist, then push local additions/removals to SC. Used by the frontend sync button for explicit reconciliation.

## Files to Modify
- `web/backend/routers/buckets.py` (modify)

## Implementation Details

### Pydantic response model
```python
class SyncSoundCloudResponse(BaseModel):
    pulled: int
    pushed_adds: int
    pushed_removals: int
    skipped: int
    errors: list[str]
```

### Endpoint: `POST /api/buckets/{bucket_id}/sync-soundcloud`

**Non-async** (`def`, not `async def`) — FastAPI runs in threadpool since SC API calls are blocking.

1. **Resolve IDs**: Query `bucket_playlist_links` + `playlists` to get `linked_playlist_id` and `soundcloud_playlist_id`. Return 400 if bucket not linked or playlist has no SC ID.

2. **Auth**: `get_web_provider_state()`. Return 401 if None.

3. **PULL phase**:
   - Call `get_playlist_tracks(state, soundcloud_playlist_id)` — returns `(new_state, track_list, created_at)` 3-tuple
   - **Must capture `new_state`**: `state, tracks, _ = get_playlist_tracks(state, sc_playlist_id)`
   - `tracks` is a list of `(sc_track_id, metadata)` tuples
   - For each SC track, look up local track: `SELECT id FROM tracks WHERE soundcloud_id = ?`
   - Check if already in local playlist: `SELECT 1 FROM playlist_tracks WHERE playlist_id = ? AND track_id = ?`
   - If found locally but NOT in playlist_tracks → INSERT with next position
   - Count as `pulled`

4. **PUSH phase** (thread state through all API calls):
   - Get local playlist tracks with SC IDs: `SELECT t.soundcloud_id FROM playlist_tracks pt JOIN tracks t ON pt.track_id = t.id WHERE pt.playlist_id = ? AND t.soundcloud_id IS NOT NULL`
   - Build set of local SC IDs (count tracks without `soundcloud_id` as `skipped`)
   - Build set of remote SC IDs (from pull phase)
   - **Additions** (in local, not in remote): thread state through loop:
     ```python
     for sc_track_id in additions:
         state, success, error = add_track_to_playlist(state, sc_playlist_id, sc_track_id)
         if success: pushed_adds += 1
         elif error: errors.append(error)
     ```
   - **Removals** (in remote, not in local): same pattern with `remove_track_from_playlist`

5. **Return**: `SyncSoundCloudResponse(pulled=..., pushed_adds=..., pushed_removals=..., skipped=..., errors=[...])`

### Key imports
```python
from music_minion.core.database import get_db_connection
from web.backend.soundcloud_auth import get_web_provider_state
from music_minion.domain.library.providers.soundcloud.api import (
    add_track_to_playlist,
    remove_track_from_playlist,
    get_playlist_tracks as sc_get_playlist_tracks,
)
```

## Verification
- `curl -X POST http://localhost:8642/api/buckets/{bucket_id}/sync-soundcloud`
- Verify response has pull/push/skip counts
- Check database for new playlist_tracks entries after pull
- Check SoundCloud (via API or web) for added/removed tracks after push
- Test 400 on non-linked bucket
- Test 401 when SC not authenticated
