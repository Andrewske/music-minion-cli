---
task: 03-refresh-on-sync
status: done
depends:
  - 01-create-refresh-function
files:
  - path: src/music_minion/commands/library.py
    action: modify
---

# Refresh Smart Playlists During Sync

## Context
When `sync local` runs and adds/removes tracks from the library, smart playlist materialized views need to be refreshed to include new tracks that match filters.

## Files to Modify/Create
- src/music_minion/commands/library.py (modify)

## Implementation Details

Find the `sync_library()` function (around line 520). After `batch_insert_provider_tracks()` completes and stats are logged (~line 670), refresh all smart playlists:

```python
# Around line 670, after:
stats = batch_insert_provider_tracks(provider_tracks, provider_name)
log("✓ Import complete!", level="info")
# ... logging ...

# Add refresh call here:
if stats["created"] > 0:
    _refresh_all_smart_playlists()
```

Add helper function at module level:

```python
def _refresh_all_smart_playlists() -> None:
    """Refresh materialized tracks for all smart playlists."""
    from music_minion.domain.playlists.crud import get_all_playlists
    from music_minion.domain.playlists.filters import refresh_smart_playlist_tracks

    playlists = get_all_playlists()
    smart_playlists = [p for p in playlists if p.get("type") == "smart"]

    if smart_playlists:
        logger.info(f"Refreshing {len(smart_playlists)} smart playlist(s)")
        for playlist in smart_playlists:
            try:
                count = refresh_smart_playlist_tracks(playlist["id"])
                logger.debug(f"Refreshed '{playlist['name']}': {count} tracks")
            except Exception as e:
                logger.warning(f"Failed to refresh smart playlist '{playlist['name']}': {e}")
```

Note: `get_all_playlists()` already exists in crud.py (line 247).

## Verification
```bash
# 1. Add a new track file to the music folder that matches a smart playlist filter
# 2. Run sync
uv run music-minion
# > sync local

# 3. Check that smart playlist track count increased
```
