---
task: 04-simplify-get-playlist-tracks
status: done
depends:
  - 01-create-refresh-function
  - 02-integrate-refresh-with-filter-crud
files:
  - path: src/music_minion/domain/playlists/crud.py
    action: modify
---

# Simplify Playlist Query Functions

## Context
Now that smart playlists store tracks in `playlist_tracks`, we can remove the branching logic that called `evaluate_filters()` for smart playlists. Both manual and smart playlists use the same query path.

This task updates FOUR functions that branch on playlist type:
1. `get_playlist_tracks()` - main track fetching
2. `get_available_playlist_tracks()` - playback file paths
3. `get_playlist_track_count()` - optimized count
4. `update_playlist_track_count()` - denormalized count update

## Files to Modify/Create
- src/music_minion/domain/playlists/crud.py (modify)

## Implementation Details

Simplify `get_playlist_tracks()` to remove the type branching:

### Before:
```python
def get_playlist_tracks(playlist_id: int) -> list[dict[str, Any]]:
    playlist = get_playlist_by_id(playlist_id)
    if not playlist:
        return []

    with get_db_connection() as conn:
        if playlist["type"] == "manual":
            # Query playlist_tracks
            cursor = conn.execute(...)
            return [dict(row) for row in cursor.fetchall()]
        else:
            # Smart playlist - evaluate filters
            return filters.evaluate_filters(playlist_id)
```

### After:
```python
def get_playlist_tracks(playlist_id: int) -> list[dict[str, Any]]:
    """Get all tracks in a playlist (works for both manual and smart)."""
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            SELECT
                t.*,
                pt.position,
                pt.added_at,
                COALESCE(per.rating, 1500.0) as playlist_elo_rating,
                COALESCE(per.comparison_count, 0) as playlist_elo_comparison_count,
                COALESCE(per.wins, 0) as playlist_elo_wins
            FROM tracks t
            JOIN playlist_tracks pt ON t.id = pt.track_id
            LEFT JOIN playlist_elo_ratings per ON t.id = per.track_id AND per.playlist_id = ?
            WHERE pt.playlist_id = ?
            ORDER BY pt.position
            """,
            (playlist_id, playlist_id),
        )
        return [dict(row) for row in cursor.fetchall()]
```

Note: Keep the existing ELO rating joins from the manual playlist query.

### 2. Simplify `get_available_playlist_tracks()` (lines 855-907)

This function gets file paths for playback. Remove the type branching:

### Before:
```python
def get_available_playlist_tracks(playlist_id: int) -> list[str]:
    playlist = get_playlist_by_id(playlist_id)
    if not playlist:
        return []

    with get_db_connection() as conn:
        if playlist["type"] == "manual":
            # Query playlist_tracks
            cursor = conn.execute(...)
        else:
            # Smart playlist - evaluate filters
            playlist_filters = filters.get_playlist_filters(playlist_id)
            ...
```

### After:
```python
def get_available_playlist_tracks(playlist_id: int) -> list[str]:
    """Get file paths of tracks in a playlist (for playback integration).
    Excludes archived tracks. Works for both manual and smart playlists.
    """
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            SELECT DISTINCT t.local_path
            FROM tracks t
            JOIN playlist_tracks pt ON t.id = pt.track_id
            LEFT JOIN ratings r ON t.id = r.track_id AND r.rating_type = 'archive'
            WHERE pt.playlist_id = ? AND r.id IS NULL
            ORDER BY pt.position
            """,
            (playlist_id,),
        )
        return [row["local_path"] for row in cursor.fetchall()]
```

### 3. Simplify `get_playlist_track_count()` (lines 444-476)

Remove filter evaluation, use unified COUNT:

### Before:
```python
def get_playlist_track_count(playlist_id: int) -> int:
    playlist = get_playlist_by_id(playlist_id)
    if not playlist:
        return 0

    with get_db_connection() as conn:
        if playlist["type"] == "manual":
            cursor = conn.execute("SELECT COUNT(*) ...")
        else:
            tracks = filters.evaluate_filters(playlist_id)
            return len(tracks)
```

### After:
```python
def get_playlist_track_count(playlist_id: int) -> int:
    """Get the number of tracks in a playlist (works for both types)."""
    with get_db_connection() as conn:
        cursor = conn.execute(
            "SELECT COUNT(*) as count FROM playlist_tracks WHERE playlist_id = ?",
            (playlist_id,),
        )
        row = cursor.fetchone()
        return row["count"] if row else 0
```

### 4. Simplify `update_playlist_track_count()` (lines 77-121)

Remove filter evaluation, use unified COUNT:

### Before:
```python
def update_playlist_track_count(playlist_id: int) -> None:
    playlist = get_playlist_by_id(playlist_id)
    if not playlist:
        return

    with get_db_connection() as conn:
        if playlist["type"] == "manual":
            cursor = conn.execute("SELECT COUNT(*) ...")
            count = cursor.fetchone()["count"]
        else:
            matching_tracks = filters.evaluate_filters(playlist_id)
            count = len(matching_tracks)
        # ... update playlists table
```

### After:
```python
def update_playlist_track_count(playlist_id: int) -> None:
    """Update the track_count field for a playlist (works for both types)."""
    with get_db_connection() as conn:
        cursor = conn.execute(
            "SELECT COUNT(*) as count FROM playlist_tracks WHERE playlist_id = ?",
            (playlist_id,),
        )
        count = cursor.fetchone()["count"]

        conn.execute(
            """
            UPDATE playlists
            SET track_count = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (count, playlist_id),
        )
        conn.commit()
```

## Verification
```bash
uv run python -c "
from music_minion.domain.playlists.crud import get_playlist_tracks, get_playlist_track_count, get_available_playlist_tracks

# Test on a smart playlist
tracks = get_playlist_tracks(375)
count = get_playlist_track_count(375)
paths = get_available_playlist_tracks(375)

print(f'get_playlist_tracks: {len(tracks)} tracks')
print(f'get_playlist_track_count: {count}')
print(f'get_available_playlist_tracks: {len(paths)} paths')
print(f'Counts match: {len(tracks) == count == len(paths)}')
"
```
