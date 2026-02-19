# humming-skipping-wave

## Overview
Fix performance issue where smart playlist queries take 9+ seconds due to type mismatch in `playlist_elo_ratings.track_id` (defined as TEXT but should be INTEGER). The mismatch prevents SQLite from using indexes on JOINs.

**Root Cause:** Schema at `database.py:951` defines `track_id TEXT NOT NULL` instead of `INTEGER`.

**Impact:** 800x performance improvement (9 seconds → 11ms) for playlist builder and other playlist queries.

## Task Sequence
1. [01-database-migration.md](./01-database-migration.md) - Add migration to convert track_id from TEXT to INTEGER
2. [02-revert-cast-workarounds.md](./02-revert-cast-workarounds.md) - Remove temporary CAST() workarounds from 7 query locations

## Success Criteria
1. Schema shows `track_id INTEGER NOT NULL`:
   ```bash
   sqlite3 ~/.local/share/music-minion/music_minion.db ".schema playlist_elo_ratings"
   ```

2. Query completes in <20ms (was 9+ seconds):
   ```bash
   time sqlite3 ~/.local/share/music-minion/music_minion.db "
   SELECT t.id, t.title, COALESCE(per.rating, 1500.0) as rating
   FROM playlist_tracks pt
   JOIN tracks t ON pt.track_id = t.id
   LEFT JOIN playlist_elo_ratings per ON pt.track_id = per.track_id
       AND per.playlist_id = pt.playlist_id
   WHERE pt.playlist_id = 381
   LIMIT 100;
   " | wc -l
   ```

3. Playlist-related tests pass:
   ```bash
   uv run pytest -k playlist -v
   ```

4. "All" playlist loads instantly in playlist builder UI

## Dependencies
- SQLite database at `~/.local/share/music-minion/music_minion.db`
- Current schema version is 35, will become 36
