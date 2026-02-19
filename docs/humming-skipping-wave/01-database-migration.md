---
task: 01-database-migration
status: done
depends: []
files:
  - path: src/music_minion/core/database.py
    action: modify
---

# Database Migration: Fix playlist_elo_ratings.track_id Type

## Context
The `playlist_elo_ratings` table has `track_id` defined as TEXT instead of INTEGER. This causes type mismatch in JOINs with other tables (where track_id is INTEGER), preventing index usage and causing 9-second query times. This migration converts the column to INTEGER.

## Files to Modify/Create
- `src/music_minion/core/database.py` (modify)

## Implementation Details

### 1. Bump Schema Version
Change line ~20:
```python
SCHEMA_VERSION = 36  # Fix playlist_elo_ratings.track_id type (TEXT → INTEGER)
```

### 2. Fix CREATE TABLE Statement
At line ~951, change:
```python
# Before
track_id TEXT NOT NULL,
# After
track_id INTEGER NOT NULL,
```

### 3. Add Migration in migrate_database()
Add migration block for version 36 (after v35, before `init_database`):
```python
if current_version < 36:
    logger.info("Migrating playlist_elo_ratings.track_id from TEXT to INTEGER...")
    try:
        # Validate: check for non-numeric track_ids that would corrupt on CAST
        cursor = conn.execute("""
            SELECT COUNT(*) FROM playlist_elo_ratings
            WHERE track_id GLOB '*[^0-9]*'
        """)
        bad_count = cursor.fetchone()[0]
        if bad_count > 0:
            raise ValueError(f"Found {bad_count} non-numeric track_id values - manual cleanup required")

        # Disable FK constraints during table recreation (follows v14 pattern)
        conn.execute("PRAGMA foreign_keys=OFF")

        # Create new table with correct type
        conn.execute("""
            CREATE TABLE playlist_elo_ratings_new (
                track_id INTEGER NOT NULL,
                playlist_id INTEGER NOT NULL,
                rating REAL DEFAULT 1500.0,
                comparison_count INTEGER DEFAULT 0,
                wins INTEGER DEFAULT 0,
                last_compared TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (track_id, playlist_id),
                FOREIGN KEY (track_id) REFERENCES tracks(id),
                FOREIGN KEY (playlist_id) REFERENCES playlists(id) ON DELETE CASCADE
            )
        """)
        # Migrate data with type conversion
        conn.execute("""
            INSERT INTO playlist_elo_ratings_new
            SELECT CAST(track_id AS INTEGER), playlist_id, rating,
                   comparison_count, wins, last_compared, updated_at
            FROM playlist_elo_ratings
        """)
        # Swap tables
        conn.execute("DROP TABLE playlist_elo_ratings")
        conn.execute("ALTER TABLE playlist_elo_ratings_new RENAME TO playlist_elo_ratings")
        # Recreate indices
        conn.execute("CREATE INDEX idx_playlist_elo_ratings_playlist_id ON playlist_elo_ratings(playlist_id, rating DESC)")
        conn.execute("CREATE INDEX idx_playlist_elo_comparison_count ON playlist_elo_ratings(playlist_id, comparison_count)")

        # Re-enable FK constraints
        conn.execute("PRAGMA foreign_keys=ON")

        conn.commit()
        logger.info("  ✓ Migration to v36 complete: playlist_elo_ratings.track_id is now INTEGER")
    except Exception as e:
        logger.error(f"  ✗ Migration to v36 failed: {e}")
        conn.rollback()
        raise
```

## Verification
1. Start the app to trigger auto-migration
2. Verify schema:
   ```bash
   sqlite3 ~/.local/share/music-minion/music_minion.db ".schema playlist_elo_ratings"
   ```
   Should show `track_id INTEGER NOT NULL`
3. Verify data preserved:
   ```bash
   sqlite3 ~/.local/share/music-minion/music_minion.db "SELECT COUNT(*) FROM playlist_elo_ratings"
   ```
