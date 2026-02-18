---
task: 05-simplify-comparisons
status: pending
depends:
  - 04-simplify-get-playlist-tracks
files:
  - path: src/music_minion/domain/rating/database.py
    action: modify
---

# Simplify Comparison Queries

## Context
Now that smart playlists have materialized tracks in `playlist_tracks`, we can remove the temp table approach and use direct JOINs for all playlists.

## Files to Modify/Create
- src/music_minion/domain/rating/database.py (modify)

## Implementation Details

Simplify `get_next_playlist_pair()` to use direct JOIN to `playlist_tracks`:

### Before (temp table approach):
```python
def get_next_playlist_pair(playlist_id: int) -> tuple[dict, dict]:
    tracks = get_playlist_tracks(playlist_id)
    track_ids = [t["id"] for t in tracks]

    with get_db_connection() as conn:
        # Create temp table
        conn.execute("DROP TABLE IF EXISTS _temp_playlist_tracks")
        conn.execute("CREATE TEMP TABLE _temp_playlist_tracks (track_id INTEGER PRIMARY KEY)")
        # Batch insert...
        # Query with JOIN to temp table...
```

### After (direct JOIN):
```python
def get_next_playlist_pair(playlist_id: int) -> tuple[dict, dict]:
    """Get next uncompared track pair for playlist ranking (stateless)."""
    import random

    with get_db_connection() as conn:
        # Check playlist has enough tracks
        cursor = conn.execute(
            "SELECT COUNT(*) as count FROM playlist_tracks WHERE playlist_id = ?",
            (playlist_id,)
        )
        track_count = cursor.fetchone()["count"]
        if track_count < 2:
            raise ValueError(f"Playlist {playlist_id} has {track_count} tracks - need at least 2")

        # Step 1: Find top 10 tracks with fewest comparisons
        cursor = conn.execute(
            """
            SELECT t.id as track_id, COUNT(pch.id) as comp_count
            FROM tracks t
            INNER JOIN playlist_tracks pt ON t.id = pt.track_id AND pt.playlist_id = ?
            LEFT JOIN playlist_comparison_history pch ON (
                (pch.track_a_id = t.id OR pch.track_b_id = t.id)
                AND pch.playlist_id = ?
            )
            GROUP BY t.id
            ORDER BY comp_count ASC
            LIMIT 10
            """,
            (playlist_id, playlist_id),
        )
        candidates = cursor.fetchall()

        if not candidates:
            raise RankingComplete(f"All pairs in playlist {playlist_id} have been compared")

        track_a_id = random.choice(candidates)["track_id"]

        # Step 2: Find another track it hasn't been compared to
        cursor = conn.execute(
            """
            SELECT t.*,
                   COALESCE(per.rating, 1500.0) as rating,
                   COALESCE(per.comparison_count, 0) as comparison_count
            FROM tracks t
            INNER JOIN playlist_tracks pt ON t.id = pt.track_id AND pt.playlist_id = ?
            LEFT JOIN playlist_elo_ratings per ON t.id = per.track_id AND per.playlist_id = ?
            LEFT JOIN playlist_comparison_history pch ON (
                pch.playlist_id = ?
                AND (
                    (pch.track_a_id = ? AND pch.track_b_id = t.id)
                    OR (pch.track_b_id = ? AND pch.track_a_id = t.id)
                )
            )
            WHERE t.id != ?
              AND pch.id IS NULL
            ORDER BY per.comparison_count ASC, RANDOM()
            LIMIT 1
            """,
            (playlist_id, playlist_id, playlist_id, track_a_id, track_a_id, track_a_id),
        )
        track_b_row = cursor.fetchone()
        # ... rest of function
```

Also remove the `get_playlist_tracks` import if no longer used.

## Verification
```bash
# Start web app
uv run music-minion --web

# In browser:
# 1. Navigate to Comparisons page
# 2. Select smart playlist (e.g., "All" with 5000+ tracks)
# 3. Verify pairs load without hanging
# 4. Check backend logs - no temp table warnings
```
