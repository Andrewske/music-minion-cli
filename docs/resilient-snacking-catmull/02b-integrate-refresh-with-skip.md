---
task: 02b-integrate-refresh-with-skip
status: done
depends:
  - 01-create-refresh-function
files:
  - path: src/music_minion/domain/playlists/builder.py
    action: modify
---

# Integrate Refresh with Skip/Unskip Operations

## Context
When users skip tracks in smart playlists, the track is added to `playlist_builder_skipped` but remains in the materialized `playlist_tracks` until the next refresh. This causes skipped tracks to reappear in the UI.

**Hybrid approach:**
- **Skip:** Targeted DELETE from `playlist_tracks` (instant, no full refresh)
- **Unskip:** Full refresh via `refresh_smart_playlist_tracks()` (needs to re-evaluate filters)

## Files to Modify/Create
- src/music_minion/domain/playlists/builder.py (modify)

## Implementation Details

### 1. Modify `skip_track()` function (~line 260)

After inserting into `playlist_builder_skipped`, also delete from `playlist_tracks`:

```python
def skip_track(playlist_id: int, track_id: int) -> bool:
    """Skip a track - exclude it from the playlist.

    For smart playlists, also removes from materialized playlist_tracks.
    """
    with get_db_connection() as conn:
        # Insert into skipped table (existing logic)
        conn.execute(
            """
            INSERT OR IGNORE INTO playlist_builder_skipped
            (playlist_id, track_id, skipped_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            """,
            (playlist_id, track_id),
        )

        # For smart playlists: also remove from materialized tracks
        # This is safe for manual playlists too (no-op if track not there via smart logic)
        conn.execute(
            "DELETE FROM playlist_tracks WHERE playlist_id = ? AND track_id = ?",
            (playlist_id, track_id),
        )

        # Update track_count
        conn.execute(
            "UPDATE playlists SET track_count = track_count - 1 WHERE id = ? AND track_count > 0",
            (playlist_id,),
        )

        conn.commit()
        return True
```

### 2. Modify `unskip_track()` function (~line 321)

After deleting from `playlist_builder_skipped`, trigger full refresh for smart playlists:

```python
def unskip_track(playlist_id: int, track_id: int) -> bool:
    """Unskip a track - include it back in the playlist.

    For smart playlists, triggers full refresh to re-evaluate filters.
    """
    from music_minion.domain.playlists.crud import get_playlist_by_id
    from music_minion.domain.playlists.filters import refresh_smart_playlist_tracks

    with get_db_connection() as conn:
        # Delete from skipped table (existing logic)
        cursor = conn.execute(
            "DELETE FROM playlist_builder_skipped WHERE playlist_id = ? AND track_id = ?",
            (playlist_id, track_id),
        )

        if cursor.rowcount == 0:
            return False  # Track wasn't skipped

        conn.commit()

    # For smart playlists: refresh to re-add the track if it still matches filters
    playlist = get_playlist_by_id(playlist_id)
    if playlist and playlist["type"] == "smart":
        refresh_smart_playlist_tracks(playlist_id)

    return True
```

## Why Hybrid Approach?

1. **Skip is common, unskip is rare:** Most users skip tracks far more often than unskipping
2. **Skip should be instant:** Targeted DELETE is O(1), full refresh is O(n)
3. **Unskip needs filter evaluation:** The track might no longer match filters, so we need full refresh anyway
4. **Simplicity:** Unskip reuses existing refresh logic rather than duplicating filter evaluation

## Verification
```bash
# Start web app
uv run music-minion --web

# In browser:
# 1. Open a smart playlist
# 2. Skip a track - verify it disappears immediately
# 3. Check track count decremented
# 4. Unskip the track - verify it reappears (if still matches filters)
# 5. Check track count restored
```
