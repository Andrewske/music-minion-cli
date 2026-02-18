---
task: 01-fix-get-next-playlist-pair
status: pending
depends:
  - 00-delete-dead-leaderboard-code
files:
  - path: src/music_minion/domain/rating/database.py
    action: modify
---

# Fix get_next_playlist_pair() for Smart Playlists

## Context
`get_next_playlist_pair()` fails for smart playlists because it directly queries `playlist_tracks` table, which is empty for smart playlists. Smart playlists store filter rules and compute tracks dynamically via `evaluate_filters()`.

## Files to Modify
- src/music_minion/domain/rating/database.py (modify)

## Implementation Details

### Step 1: Add import at top of module

Add with other imports at top of file:
```python
from music_minion.domain.playlists.crud import get_playlist_tracks
```

### Step 2: Replace validation (lines 291-300)

```python
# Get playlist tracks - works for both manual and smart playlists
tracks = get_playlist_tracks(playlist_id)
if len(tracks) < 2:
    raise ValueError(
        f"Playlist {playlist_id} has {len(tracks)} tracks - need at least 2 for comparison"
    )
track_ids = [t["id"] for t in tracks]
```

### Step 3: Replace Step 1 query (lines 303-317)

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

### Step 4: Replace Step 2 query (lines 330-359)

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

## Verification
```bash
uv run pytest src/music_minion/domain/rating/ -v
```
