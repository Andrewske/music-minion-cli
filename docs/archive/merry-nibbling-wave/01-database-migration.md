---
task: 01-database-migration
status: done
depends: []
files:
  - path: src/music_minion/core/database.py
    action: modify
---

# Database Migration and Schema Updates

## Context
Migrate global ELO rankings and comparison history to the "All" smart playlist, then drop old global tables. This consolidates from 4 tables to 2, enabling a single playlist-based comparison mode. Includes performance indexes and data integrity constraints.

## Files to Modify/Create
- src/music_minion/core/database.py (modify)

## Implementation Details

### 1. Migrate Global Data to "All" Playlist
Add migration SQL in `initialize_database()`:

```sql
-- Find "All" playlist ID
WITH all_playlist AS (
    SELECT id FROM playlists WHERE name = 'All' LIMIT 1
)

-- Copy global ELO ratings to playlist ratings for "All"
INSERT INTO playlist_elo_ratings (track_id, playlist_id, rating, comparison_count, wins, losses)
SELECT
    er.track_id,
    (SELECT id FROM all_playlist) as playlist_id,
    er.rating,
    er.comparison_count,
    er.wins,
    MAX(0, er.comparison_count - er.wins) as losses
FROM elo_ratings er
WHERE EXISTS (SELECT 1 FROM all_playlist)
ON CONFLICT (track_id, playlist_id) DO UPDATE SET
    rating = excluded.rating,
    comparison_count = excluded.comparison_count,
    wins = excluded.wins,
    losses = excluded.losses;

-- Copy global comparison history to playlist history for "All"
INSERT INTO playlist_comparison_history (
    playlist_id, track_a_id, track_b_id, winner_id,
    track_a_rating_before, track_b_rating_before,
    track_a_rating_after, track_b_rating_after,
    session_id, timestamp
)
SELECT
    (SELECT id FROM all_playlist) as playlist_id,
    ch.track_a_id, ch.track_b_id, ch.winner_id,
    ch.track_a_rating_before, ch.track_b_rating_before,
    ch.track_a_rating_after, ch.track_b_rating_after,
    ch.session_id, ch.timestamp
FROM comparison_history ch
WHERE EXISTS (SELECT 1 FROM all_playlist);
```

### 2. Add Migration Logging
Log stats after migration for verification:

```python
with get_db_connection() as conn:
    cursor = conn.execute("SELECT id FROM playlists WHERE name = 'All'")
    all_playlist = cursor.fetchone()

    if all_playlist:
        all_id = all_playlist['id']

        # Count what was migrated
        cursor = conn.execute("SELECT COUNT(*) FROM elo_ratings")
        old_ratings = cursor.fetchone()[0]

        cursor = conn.execute(
            "SELECT COUNT(*) FROM playlist_elo_ratings WHERE playlist_id = ?",
            (all_id,)
        )
        new_ratings = cursor.fetchone()[0]

        cursor = conn.execute("SELECT COUNT(*) FROM comparison_history")
        old_comparisons = cursor.fetchone()[0]

        cursor = conn.execute(
            "SELECT COUNT(*) FROM playlist_comparison_history WHERE playlist_id = ?",
            (all_id,)
        )
        new_comparisons = cursor.fetchone()[0]

        logger.info(f"✅ Migration complete:")
        logger.info(f"  - Ratings: {new_ratings} / {old_ratings} migrated to All playlist")
        logger.info(f"  - Comparisons: {new_comparisons} / {old_comparisons} migrated to All playlist")

        if new_ratings != old_ratings or new_comparisons != old_comparisons:
            logger.warning(f"⚠️  Migration mismatch detected - check for data issues")
```

### 3. Add Performance Indexes
Critical for 5000-track performance. Two separate indexes for pair lookup (OR condition can't use composite):

```sql
-- Speeds up pair lookup when track is track_a
CREATE INDEX IF NOT EXISTS idx_playlist_comparison_track_a
ON playlist_comparison_history(playlist_id, track_a_id);

-- Speeds up pair lookup when track is track_b
CREATE INDEX IF NOT EXISTS idx_playlist_comparison_track_b
ON playlist_comparison_history(playlist_id, track_b_id);

-- Speeds up "tracks with fewest comparisons" queries
CREATE INDEX IF NOT EXISTS idx_playlist_elo_comparison_count
ON playlist_elo_ratings(playlist_id, comparison_count);
```

### 4. Backup and Drop Old Tables
Rename tables as backup before dropping (can be removed in future migration if all is well):

```sql
-- Backup old tables (can recover if issues found)
ALTER TABLE comparison_history RENAME TO _backup_comparison_history;
ALTER TABLE elo_ratings RENAME TO _backup_elo_ratings;
ALTER TABLE playlist_ranking_sessions RENAME TO _backup_playlist_ranking_sessions;
```

**Note:** After verifying migration is successful in production use, a future migration (v34) can drop these backup tables:
```sql
DROP TABLE IF EXISTS _backup_comparison_history;
DROP TABLE IF EXISTS _backup_elo_ratings;
DROP TABLE IF EXISTS _backup_playlist_ranking_sessions;
```

### 5. Update Schema Version
Increment `SCHEMA_VERSION` from 32 to 33 to trigger migration.

## Verification

Run verification script:
```bash
uv run python -c "
from music_minion.core.database import get_db_connection

with get_db_connection() as conn:
    # Check All playlist exists
    cursor = conn.execute('SELECT id FROM playlists WHERE name = \"All\"')
    all_playlist = cursor.fetchone()
    assert all_playlist, 'All playlist not found!'
    all_id = all_playlist['id']

    # Check ratings migrated
    cursor = conn.execute('SELECT COUNT(*) FROM playlist_elo_ratings WHERE playlist_id = ?', (all_id,))
    rating_count = cursor.fetchone()[0]
    print(f'✅ All playlist has {rating_count} rated tracks')

    # Check comparisons migrated
    cursor = conn.execute('SELECT COUNT(*) FROM playlist_comparison_history WHERE playlist_id = ?', (all_id,))
    comparison_count = cursor.fetchone()[0]
    print(f'✅ All playlist has {comparison_count} comparison records')

    # Check old tables renamed to backup
    cursor = conn.execute(\"\"\"
        SELECT name FROM sqlite_master
        WHERE type='table'
        AND name IN ('_backup_elo_ratings', '_backup_comparison_history', '_backup_playlist_ranking_sessions')
    \"\"\")
    backup_tables = cursor.fetchall()
    assert len(backup_tables) == 3, f'Backup tables missing: {backup_tables}'
    print('✅ Old tables backed up')

    # Check indexes exist (3 indexes now)
    cursor = conn.execute(\"\"\"
        SELECT name FROM sqlite_master
        WHERE type='index'
        AND name IN ('idx_playlist_comparison_track_a', 'idx_playlist_comparison_track_b', 'idx_playlist_elo_comparison_count')
    \"\"\")
    indexes = cursor.fetchall()
    assert len(indexes) == 3, f'Missing performance indexes: got {len(indexes)}'
    print('✅ Performance indexes created')
"
```

Expected output:
- ✅ All playlist has {N} rated tracks
- ✅ All playlist has {M} comparison records
- ✅ Old tables backed up
- ✅ Performance indexes created
