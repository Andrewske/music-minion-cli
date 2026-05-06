---
task: 02-backend-sync-logic
status: pending
depends: [01-backend-surface-sc-id]
files:
  - path: web/backend/routers/buckets.py
    action: modify
---

# Backend Sync Endpoint and Logic

## Context
The core sync logic: a new function that does pull-then-push bidirectional sync between a bucket's linked playlist and SoundCloud. Plus the router endpoint to expose it.

## Files to Modify
- `web/backend/routers/buckets.py` (modify) — add sync logic inline + endpoint

## Implementation Details

### Sync function: `sync_bucket_soundcloud(bucket_id: str) -> dict` (inline in router)

Place this as a helper function in `web/backend/routers/buckets.py` (matches pattern in `routers/playlists.py:569-641`).

1. **Resolve IDs**: Join `bucket_playlist_links` + `playlists` to get `linked_playlist_id` and `soundcloud_playlist_id`. Return error dict if missing.

2. **Auth**: Use `get_provider_state("soundcloud")` from `src/music_minion/domain/playlists/sync.py` and `providers.get_provider("soundcloud")` from `src/music_minion/domain/library/providers`.

3. **PULL phase**:
   - Call `provider.get_playlist_tracks(state, soundcloud_playlist_id)` — returns `(new_state, track_list, created_at)` (3-tuple, see `sync.py:272` for reference)
   - **Must capture `new_state`**: `state, tracks, _ = provider.get_playlist_tracks(state, soundcloud_playlist_id)`
   - `tracks` is a list of `(sc_track_id, metadata)` tuples
   - For each SC track, look up local track: `SELECT id FROM tracks WHERE soundcloud_id = ?`
   - Check if already in local playlist: `SELECT 1 FROM playlist_tracks WHERE playlist_id = ? AND track_id = ?`
   - If found locally but NOT in playlist_tracks → INSERT with next position
   - Count as `pulled`

4. **PUSH phase** (thread state through all API calls):
   - Get local playlist tracks with SC IDs: `SELECT t.soundcloud_id FROM playlist_tracks pt JOIN tracks t ON pt.track_id = t.id WHERE pt.playlist_id = ?`
   - Build set of local SC IDs (skip nulls, count as `skipped`)
   - Build set of remote SC IDs (from pull phase)
   - **Additions** (in local, not in remote): thread state through loop:
     ```python
     for sc_track_id in additions:
         state, success, error = provider.add_track_to_playlist(state, sc_playlist_id, sc_track_id)
         if success: pushed_adds += 1
         elif error: errors.append(error)
     ```
   - **Removals** (in remote, not in local): same pattern:
     ```python
     for sc_track_id in removals:
         state, success, error = provider.remove_track_from_playlist(state, sc_playlist_id, sc_track_id)
         if success: pushed_removals += 1
         elif error: errors.append(error)
     ```
   - Note: No rate limiting — accepted risk for personal project with small playlists.

5. **Finalize**: Call `update_playlist_last_synced(playlist_id)` from sync module. Update `playlists.track_count`.

6. **Return**: `{"pulled": N, "pushed_adds": N, "pushed_removals": N, "skipped": N, "errors": [...]}`

### Router endpoint

```python
class SyncSoundCloudResponse(BaseModel):
    pulled: int
    pushed_adds: int
    pushed_removals: int
    skipped: int
    errors: list[str]

@router.post("/{bucket_id}/sync-soundcloud", response_model=SyncSoundCloudResponse)
def sync_bucket_soundcloud_endpoint(bucket_id: str):
    """Non-async: FastAPI runs in threadpool since SC API calls are blocking."""
    result = sync_bucket_soundcloud(bucket_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result
```

### Key imports to reuse
- `from music_minion.domain.playlists.sync import get_provider_state, update_playlist_last_synced`
- `from music_minion.domain.library import providers`

## Verification
- `curl -X POST http://localhost:8642/api/buckets/{bucket_id}/sync-soundcloud`
- Verify response has pull/push counts
- Check database for new playlist_tracks entries after pull
- Check SoundCloud (via API or web) for added/removed tracks after push
