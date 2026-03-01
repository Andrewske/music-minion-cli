---
task: 01-database-migration
status: done
depends: []
files:
  - path: src/music_minion/core/database.py
    action: modify
---

# Database Migration v47: Composite Provider ID Indexes

## Context

Currently `soundcloud_id` has a single-column unique constraint, preventing both a local track and a SoundCloud track from having the same `soundcloud_id`. This migration changes the constraint to `(source, soundcloud_id)`, allowing both records to coexist.

## Files to Modify/Create

- `src/music_minion/core/database.py` (modify)

## Implementation Details

1. **Increment SCHEMA_VERSION** from 46 to 47 (line ~20)

2. **Add migration block** at the end of `migrate_database()` function:

```python
if current_version < 47:
    logger.info("Migrating to v47: Composite unique index for track provider IDs...")

    # Drop old single-column unique indexes
    conn.execute("DROP INDEX IF EXISTS idx_tracks_soundcloud_id")
    conn.execute("DROP INDEX IF EXISTS idx_tracks_spotify_id")
    conn.execute("DROP INDEX IF EXISTS idx_tracks_youtube_id")

    # Create new composite unique indexes with source
    conn.execute("""
        CREATE UNIQUE INDEX idx_tracks_soundcloud_id
        ON tracks (source, soundcloud_id)
        WHERE soundcloud_id IS NOT NULL
    """)
    conn.execute("""
        CREATE UNIQUE INDEX idx_tracks_spotify_id
        ON tracks (source, spotify_id)
        WHERE spotify_id IS NOT NULL
    """)
    conn.execute("""
        CREATE UNIQUE INDEX idx_tracks_youtube_id
        ON tracks (source, youtube_id)
        WHERE youtube_id IS NOT NULL
    """)

    conn.commit()
    logger.info("  ✓ Migration to v47 complete")
```

3. **Update CREATE TABLE statements** to use composite indexes for new databases:

   **Line ~485** (in v11 migration block):
   ```python
   # Change from:
   "CREATE UNIQUE INDEX IF NOT EXISTS idx_tracks_soundcloud_id ON tracks (soundcloud_id) WHERE soundcloud_id IS NOT NULL"
   # To:
   "CREATE UNIQUE INDEX IF NOT EXISTS idx_tracks_soundcloud_id ON tracks (source, soundcloud_id) WHERE soundcloud_id IS NOT NULL"
   ```

   Apply same change to `spotify_id` and `youtube_id` indexes.

   **Line ~626** (in v14 migration block):
   ```python
   # Same changes for all three indexes
   "CREATE UNIQUE INDEX IF NOT EXISTS idx_tracks_soundcloud_id ON tracks (source, soundcloud_id) WHERE soundcloud_id IS NOT NULL"
   "CREATE UNIQUE INDEX IF NOT EXISTS idx_tracks_spotify_id ON tracks (source, spotify_id) WHERE spotify_id IS NOT NULL"
   "CREATE UNIQUE INDEX IF NOT EXISTS idx_tracks_youtube_id ON tracks (source, youtube_id) WHERE youtube_id IS NOT NULL"
   ```

   **Why**: Without updating CREATE TABLE, fresh database installs get old single-column indexes, causing schema drift.

## Verification

1. Run `music-minion` to trigger migration
2. Verify schema version:
   ```bash
   sqlite3 ~/.local/share/music-minion/music_minion.db "SELECT version FROM schema_version"
   # Expected: 47
   ```
3. Test constraint allows both sources:
   ```sql
   INSERT INTO tracks (title, source, soundcloud_id) VALUES ('Test', 'local', '123');
   INSERT INTO tracks (title, source, soundcloud_id) VALUES ('Test', 'soundcloud', '123');
   -- Should succeed (was error before)
   ```
