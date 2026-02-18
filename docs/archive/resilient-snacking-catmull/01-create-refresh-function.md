---
task: 01-create-refresh-function
status: done
depends: []
files:
  - path: src/music_minion/domain/playlists/filters.py
    action: modify
---

# Create Smart Playlist Refresh Function

## Context
Smart playlists currently compute tracks dynamically on every query. We need a function to materialize the filter results into `playlist_tracks` table, enabling unified handling with manual playlists.

## Files to Modify/Create
- src/music_minion/domain/playlists/filters.py (modify)

## Implementation Details

Add a new function `refresh_smart_playlist_tracks()` to filters.py:

```python
def refresh_smart_playlist_tracks(playlist_id: int) -> int:
    """Re-evaluate filters and update playlist_tracks table.

    Returns number of tracks after refresh.
    """
    # 1. Get current filter results
    tracks = evaluate_filters(playlist_id)
    track_ids = [t["id"] for t in tracks]

    with get_db_connection() as conn:
        # 2. Clear existing playlist_tracks for this playlist
        conn.execute("DELETE FROM playlist_tracks WHERE playlist_id = ?", (playlist_id,))

        # 3. Insert new tracks with positions (batch insert for performance)
        conn.executemany(
            """
            INSERT INTO playlist_tracks (playlist_id, track_id, position, added_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """,
            [(playlist_id, track_id, position) for position, track_id in enumerate(track_ids)]
        )

        # 4. Update playlist track_count
        conn.execute(
            "UPDATE playlists SET track_count = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (len(track_ids), playlist_id)
        )

        conn.commit()

    return len(track_ids)
```

Key considerations:
- Use `executemany` for batch insert (performance)
- Update `updated_at` timestamp on playlist
- Single transaction for atomicity

## Verification
```bash
# Test the function manually
uv run python -c "
from music_minion.domain.playlists.filters import refresh_smart_playlist_tracks
# Use a known smart playlist ID
count = refresh_smart_playlist_tracks(375)
print(f'Refreshed playlist with {count} tracks')
"
```
