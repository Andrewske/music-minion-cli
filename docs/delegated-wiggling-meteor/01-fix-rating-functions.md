---
task: 01-fix-rating-functions-for-smart-playlists
status: pending
depends: []
files:
  - path: src/music_minion/domain/rating/database.py
    action: modify
---

# Fix Rating Functions for Smart Playlists

## Context
Four functions in `rating/database.py` fail for smart playlists because they directly query `playlist_tracks` table, which is empty for smart playlists. Smart playlists store filter rules and compute tracks dynamically via `evaluate_filters()`.

Functions to fix:
- `get_next_playlist_pair()` (line 270)
- `get_playlist_leaderboard()` (line 48)
- `get_playlist_tracks_by_rating()` (line 466)

## Files to Modify/Create
- src/music_minion/domain/rating/database.py (modify)

## Implementation Details

### Step 1: Add imports at top of module

Add with other imports at top of file:
```python
from music_minion.domain.playlists.crud import get_playlist_tracks
```

### Step 2: Fix get_next_playlist_pair() (lines 270-381)

1. **Replace validation (lines 291-300):**
```python
# Get playlist tracks - works for both manual and smart playlists
tracks = get_playlist_tracks(playlist_id)
if len(tracks) < 2:
    raise ValueError(
        f"Playlist {playlist_id} has {len(tracks)} tracks - need at least 2 for comparison"
    )
track_ids = [t["id"] for t in tracks]
```

2. **Replace Step 1 query (lines 303-317):**
Change from `JOIN playlist_tracks pt` to use track_ids:
```python
cursor = conn.execute(
    f"""
    SELECT t.id as track_id, COUNT(pch.id) as comp_count
    FROM tracks t
    LEFT JOIN playlist_comparison_history pch ON (
        (pch.track_a_id = t.id OR pch.track_b_id = t.id)
        AND pch.playlist_id = ?
    )
    WHERE t.id IN ({','.join('?' * len(track_ids))})
    GROUP BY t.id
    ORDER BY comp_count ASC
    LIMIT 10
    """,
    (playlist_id,) + tuple(track_ids),
)
```

3. **Replace Step 2 query (lines 330-359):**
Same pattern - replace `JOIN playlist_tracks pt WHERE pt.playlist_id = ?` with `WHERE t.id IN (track_ids)`:
```python
cursor = conn.execute(
    f"""
    SELECT t.*,
           COALESCE(per.rating, 1500.0) as rating,
           COALESCE(per.comparison_count, 0) as comparison_count
    FROM tracks t
    LEFT JOIN playlist_elo_ratings per ON t.id = per.track_id AND per.playlist_id = ?
    LEFT JOIN playlist_comparison_history pch ON (
        pch.playlist_id = ?
        AND (
            (pch.track_a_id = ? AND pch.track_b_id = t.id)
            OR (pch.track_b_id = ? AND pch.track_a_id = t.id)
        )
    )
    WHERE t.id IN ({','.join('?' * len(track_ids))})
      AND t.id != ?
      AND pch.id IS NULL
    ORDER BY per.comparison_count ASC, RANDOM()
    LIMIT 1
    """,
    (playlist_id, playlist_id, track_a_id, track_a_id) + tuple(track_ids) + (track_a_id,),
)
```

### Step 3: Fix get_playlist_leaderboard() (lines 48-97)

Same pattern - get track IDs first, use IN clause:

```python
def get_playlist_leaderboard(
    playlist_id: int,
    limit: int = 50,
    min_comparisons: int = 1,
) -> list[dict]:
    # Get track IDs for this playlist (handles both manual and smart)
    tracks = get_playlist_tracks(playlist_id)
    if not tracks:
        return []
    track_ids = [t["id"] for t in tracks]

    with get_db_connection() as conn:
        cursor = conn.execute(
            f"""
            SELECT
                t.id, t.title, t.artist, t.album, t.genre, t.year,
                t.local_path, t.soundcloud_id, t.spotify_id, t.youtube_id,
                t.source, t.duration,
                COALESCE(per.rating, 1500.0) as playlist_rating,
                COALESCE(per.comparison_count, 0) as playlist_comparison_count,
                COALESCE(per.wins, 0) as playlist_wins,
                COALESCE(per.losses, 0) as playlist_losses
            FROM tracks t
            LEFT JOIN playlist_elo_ratings per ON t.id = per.track_id AND per.playlist_id = ?
            WHERE t.id IN ({','.join('?' * len(track_ids))})
              AND COALESCE(per.comparison_count, 0) >= ?
            ORDER BY COALESCE(per.rating, 1500.0) DESC, per.comparison_count DESC
            LIMIT ?
            """,
            (playlist_id,) + tuple(track_ids) + (min_comparisons, limit),
        )
        return [dict(row) for row in cursor.fetchall()]
```

### Step 4: Fix get_playlist_tracks_by_rating() (lines 466-511)

Same pattern:

```python
def get_playlist_tracks_by_rating(
    playlist_id: int,
    limit: int = 50,
    min_comparisons: int = 1,
) -> list[dict]:
    # Get track IDs for this playlist (handles both manual and smart)
    tracks = get_playlist_tracks(playlist_id)
    if not tracks:
        return []
    track_ids = [t["id"] for t in tracks]

    with get_db_connection() as conn:
        cursor = conn.execute(
            f"""
            SELECT
                t.id, t.title, t.artist, t.album, t.genre, t.year,
                t.local_path, t.soundcloud_id, t.spotify_id, t.youtube_id,
                t.source, t.duration,
                COALESCE(per.rating, 1500.0) as rating,
                COALESCE(per.comparison_count, 0) as comparison_count,
                COALESCE(per.wins, 0) as wins,
                COALESCE(per.losses, 0) as losses
            FROM tracks t
            LEFT JOIN playlist_elo_ratings per ON t.id = per.track_id AND per.playlist_id = ?
            WHERE t.id IN ({','.join('?' * len(track_ids))})
              AND COALESCE(per.comparison_count, 0) >= ?
            ORDER BY COALESCE(per.rating, 1500.0) DESC, per.comparison_count DESC
            LIMIT ?
            """,
            (playlist_id,) + tuple(track_ids) + (min_comparisons, limit),
        )
        return [dict(row) for row in cursor.fetchall()]
```

## Verification
```bash
uv run pytest src/music_minion/domain/rating/ -v
```
