---
task: 02-revert-cast-workarounds
status: done
depends: [01-database-migration]
files:
  - path: web/backend/routers/playlists.py
    action: modify
  - path: src/music_minion/domain/playlists/crud.py
    action: modify
  - path: src/music_minion/domain/playlists/filters.py
    action: modify
  - path: src/music_minion/domain/playlists/analytics.py
    action: modify
  - path: src/music_minion/domain/rating/database.py
    action: modify
---

# Revert CAST Workarounds

## Context
Temporary `CAST(... AS TEXT)` workarounds were added to work around the type mismatch. Now that the database schema is fixed (track_id is INTEGER), these casts should be reverted to use direct integer comparison for proper index usage.

## Files to Modify/Create
- `web/backend/routers/playlists.py` (modify - 1 place)
- `src/music_minion/domain/playlists/crud.py` (modify - 2 places)
- `src/music_minion/domain/playlists/filters.py` (modify - 1 place)
- `src/music_minion/domain/playlists/analytics.py` (modify - 1 place)
- `src/music_minion/domain/rating/database.py` (modify - 2 places)

## Implementation Details

### 1. web/backend/routers/playlists.py
Find and revert:
```python
# Before (with workaround)
LEFT JOIN playlist_elo_ratings per ON CAST(pt.track_id AS TEXT) = per.track_id
# After (clean)
LEFT JOIN playlist_elo_ratings per ON pt.track_id = per.track_id
```

### 2. src/music_minion/domain/playlists/crud.py (2 places)
Find and revert both:
```python
# Before (with workaround)
LEFT JOIN playlist_elo_ratings per ON CAST(pt.track_id AS TEXT) = per.track_id
LEFT JOIN playlist_elo_ratings per ON CAST(t.id AS TEXT) = per.track_id
# After (clean)
LEFT JOIN playlist_elo_ratings per ON pt.track_id = per.track_id
LEFT JOIN playlist_elo_ratings per ON t.id = per.track_id
```

### 3. src/music_minion/domain/playlists/filters.py
Find and revert:
```python
# Before (with workaround)
LEFT JOIN playlist_elo_ratings per ON CAST(t.id AS TEXT) = per.track_id
# After (clean)
LEFT JOIN playlist_elo_ratings per ON t.id = per.track_id
```

### 4. src/music_minion/domain/playlists/analytics.py
Find and revert:
```python
# Before (with workaround)
LEFT JOIN playlist_elo_ratings per ON CAST(pt.track_id AS TEXT) = per.track_id
# After (clean)
LEFT JOIN playlist_elo_ratings per ON pt.track_id = per.track_id
```

### 5. src/music_minion/domain/rating/database.py (2 places)
Find and revert both:
```python
# Before (with workaround)
LEFT JOIN playlist_elo_ratings per ON CAST(t.id AS TEXT) = per.track_id
# After (clean)
LEFT JOIN playlist_elo_ratings per ON t.id = per.track_id
```

## Verification
1. Test query speed (should be <20ms):
   ```bash
   time sqlite3 ~/.local/share/music-minion/music_minion.db "
   SELECT t.id, t.title, COALESCE(per.rating, 1500.0) as rating
   FROM playlist_tracks pt
   JOIN tracks t ON pt.track_id = t.id
   LEFT JOIN playlist_elo_ratings per ON pt.track_id = per.track_id
       AND per.playlist_id = pt.playlist_id
   WHERE pt.playlist_id = 381
   ORDER BY t.artist ASC
   LIMIT 100;
   " | wc -l
   ```
2. Run playlist-related tests:
   ```bash
   uv run pytest -k playlist -v
   ```
