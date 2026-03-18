---
task: 01-backend-waveform-endpoints
status: done
depends: []
files:
  - path: web/backend/routers/tracks.py
    action: modify
---

# Backend: Waveform Cache Delete + Bulk Purge Endpoints

## Context
SoundCloud waveform cache files (`~/.local/share/music-minion/waveforms/{track_id}.json`) are never refreshed once written. Need two new endpoints to allow cache invalidation.

## Files to Modify/Create
- `web/backend/routers/tracks.py` (modify)

## Implementation Details

### DELETE /api/tracks/{track_id}/waveform
Deletes the cached waveform JSON for a single track so the next GET re-fetches from SoundCloud. Note: intentionally does NOT check source — allows refreshing any waveform (local or SC), since the user explicitly chose to refresh this specific track.

```python
@router.delete("/tracks/{track_id}/waveform")
async def delete_waveform_cache(track_id: int):
    cache_path = get_waveform_path(track_id)
    if cache_path.exists():
        cache_path.unlink()
    return {"ok": True}
```

### POST /api/waveforms/purge-soundcloud
Deletes all cached waveform JSONs where `"source": "soundcloud"`. Locally-generated waveforms (no `source` field) are preserved.

```python
@router.post("/waveforms/purge-soundcloud")
async def purge_soundcloud_waveforms():
    cache_dir = get_waveform_cache_dir()
    count = 0
    for f in cache_dir.glob("*.json"):
        try:
            with open(f) as fh:
                data = json.load(fh)
            if data.get("source") == "soundcloud":
                f.unlink()
                count += 1
        except (json.JSONDecodeError, OSError):
            continue
    return {"purged": count}
```

**Imports:** `get_waveform_path` is already imported in tracks.py. **Add `get_waveform_cache_dir` to the existing import** from `..waveform` (line 8). `json` is already imported.

**Key detail:** `"source": "soundcloud"` is already written by `fetch_soundcloud_waveform()` at line 202 of `web/backend/waveform.py`.

## Verification
```bash
# Test single delete
curl -X DELETE http://localhost:8642/api/tracks/{some_track_id}/waveform
# Should return {"ok": true}

# Test bulk purge
curl -X POST http://localhost:8642/api/waveforms/purge-soundcloud
# Should return {"purged": N} where N = number of SC waveforms deleted

# Verify local waveforms survived
ls ~/.local/share/music-minion/waveforms/
```
