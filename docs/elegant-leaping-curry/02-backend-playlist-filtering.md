---
task: 02-backend-playlist-filtering
status: done
depends:
  - 01-database-migration
files:
  - path: web/backend/routers/playlists.py
    action: modify
  - path: web/backend/routers/player.py
    action: modify
  - path: web/backend/routers/tracks.py
    action: modify
---

# Backend: Add Library Filter to Playlists API

## Context

The frontend library switcher needs to filter playlists by library (local vs soundcloud). The backend `get_all_playlists()` already supports a `library` parameter, but the API endpoint doesn't expose it. Also fix a hardcoded `source_type="local"` in player.py.

## Files to Modify/Create

- `web/backend/routers/playlists.py` (modify)
- `web/backend/routers/player.py` (modify)

## Implementation Details

### playlists.py

Update `GET /playlists` endpoint to accept optional `library` query parameter:

```python
from typing import Optional

@router.get("/playlists")
async def get_playlists(library: Optional[str] = None):
    """Get all playlists, optionally filtered by library."""
    try:
        from music_minion.domain.playlists.crud import get_all_playlists

        playlists = get_all_playlists(library=library)
        return {"playlists": playlists}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get playlists: {str(e)}")
```

### player.py

Fix **all 4** hardcoded `start_play()` calls (lines 198, 313, 371, 455):

```python
# Before (all 4 locations)
history_id = start_play(track_id=..., source_type="local")

# After (all 4 locations)
# Line 198: track is queue_tracks[queue_index]
history_id = start_play(track_id=..., source_type=queue_tracks[queue_index].get('source', 'local'))

# Line 313: track is s.queue[new_index]
history_id = start_play(track_id=..., source_type=s.queue[new_index].get('source', 'local'))

# Line 371: track is new_tracks[0]
history_id = start_play(track_id=..., source_type=new_tracks[0].get('source', 'local'))

# Line 455: track is state.queue[new_index]
history_id = start_play(track_id=..., source_type=state.queue[new_index].get('source', 'local'))
```

### tracks.py

Update `/tracks/{id}/stream` endpoint to use SoundCloud API for authenticated streaming (faster than yt-dlp):

```python
# Replace lines 80-82 in stream_audio():
if row and row["source"] == "soundcloud" and row["source_url"]:
    from web.backend.soundcloud_auth import get_web_provider_state
    from music_minion.domain.library.providers.soundcloud.api import get_stream_url

    state = get_web_provider_state()
    if state and state.authenticated:
        # Fast path: use SC API directly (~200ms)
        stream_url = get_stream_url(state, row["soundcloud_id"])
        if stream_url:
            logger.info(f"Resolved SC stream for track {track_id}")
            return RedirectResponse(stream_url)

    # Fallback: yt-dlp for unauthenticated or API failure (~2-3s)
    from music_minion.domain.radio.stream_resolver import resolve_stream_url
    stream_url = resolve_stream_url(row["source_url"])
    if stream_url:
        logger.info(f"Resolved stream via yt-dlp for track {track_id}")
        return RedirectResponse(stream_url)

    raise HTTPException(503, "Failed to resolve stream URL")
```

## Verification

1. Test filtered endpoint:
   ```bash
   curl "http://localhost:8642/api/playlists?library=local"
   curl "http://localhost:8642/api/playlists?library=soundcloud"
   ```
2. Verify no `library` param returns all playlists
3. Play a track and check history entry has correct `source_type`
