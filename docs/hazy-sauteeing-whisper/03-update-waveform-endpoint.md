---
task: 03-update-waveform-endpoint
status: done
depends: []
files:
  - path: web/backend/routers/tracks.py
    action: modify
---

# Update Waveform Endpoint to Prioritize Local Files

## Context

The waveform endpoint currently checks `source == 'soundcloud'` first and tries the SoundCloud API, even when a local file exists. This adds unnecessary latency (10s timeout on failure) and fails for tracks without valid SC auth. Change to prioritize local files.

**Enhancement:** The SC fallback is expanded from `source='soundcloud'` tracks only to ANY track with `soundcloud_id`. This provides resilience for the 72 new local tracks - if their local files are missing/corrupted, SC waveform works as backup.

## Files to Modify/Create

- `web/backend/routers/tracks.py` (modify - lines 145-170)

## Implementation Details

Change the waveform generation logic order:

**Before (current):**
```python
if row["source"] == "soundcloud" and row["soundcloud_id"]:
    # Try SoundCloud API first...
    waveform_data = fetch_soundcloud_waveform(...)
    if waveform_data:
        return JSONResponse(waveform_data)
    # Fall through to local

# Generate from local file
file_path = get_track_path(track_id, db)
```

**After (prioritize local):**
```python
# Prioritize local file for waveform generation
file_path = get_track_path(track_id, db)
if file_path:
    validated = validate_track_path(file_path, config.music)
    if validated and validated.exists():
        logger.info(f"Generating waveform from local file for track {track_id}")
        waveform_data = generate_waveform(str(validated), track_id)
        return JSONResponse(waveform_data)

# Fallback to SoundCloud API for streaming-only tracks
if row["soundcloud_id"]:
    duration = row["duration"] or 0
    waveform_data = fetch_soundcloud_waveform(
        row["soundcloud_id"], track_id, duration
    )
    if waveform_data:
        return JSONResponse(waveform_data)

raise HTTPException(404, "No waveform source available")
```

## Verification

```bash
# Test with a track that has both local_path and soundcloud_id
curl -s "http://localhost:8642/api/tracks/6699/waveform" | head -c 100
# Should return waveform JSON quickly (no 10s delay)

# Check logs show local generation, not SC API call
tail -f music-minion-uvicorn.log | grep -i waveform
```
