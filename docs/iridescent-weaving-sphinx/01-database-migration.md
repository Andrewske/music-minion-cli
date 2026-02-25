---
task: 01-database-migration
status: done
depends: []
files:
  - path: src/music_minion/core/database.py
    action: modify
---

# Database Migration v44: Content Hash Column

## Context
Add the `file_metadata_hash` column to enable content-based change detection. This replaces unreliable mtime-based detection that fails when external editors (Serato, rekordbox) modify metadata without updating file timestamps.

## Files to Modify/Create
- src/music_minion/core/database.py (modify)

## Implementation Details

Add migration to schema version 44:

```python
if current_version < 44:
    logger.info("Migrating to v44: Content-based metadata sync...")

    # Add file_metadata_hash column for change detection
    try:
        conn.execute("ALTER TABLE tracks ADD COLUMN file_metadata_hash TEXT")
    except sqlite3.OperationalError:
        pass  # Column already exists

    # Add last_sync_direction for ping-pong detection
    try:
        conn.execute("ALTER TABLE tracks ADD COLUMN last_sync_direction TEXT")
    except sqlite3.OperationalError:
        pass  # Column already exists

    # Add sync_source for audit trail ('file', 'ui', 'api')
    try:
        conn.execute("ALTER TABLE tracks ADD COLUMN sync_source TEXT")
    except sqlite3.OperationalError:
        pass  # Column already exists

    # Note: No index needed - sync queries scan all local tracks anyway.
    # Composite indexes don't help with hash inequality comparisons.

    conn.commit()
    logger.info("  Migration to v44 complete")
```

Update `CURRENT_SCHEMA_VERSION` constant to 44.

## Verification
1. Run `music-minion` to trigger migration
2. Check database schema: `sqlite3 ~/.local/share/music-minion/library.db ".schema tracks" | grep file_metadata_hash`
3. Verify index exists: `sqlite3 ~/.local/share/music-minion/library.db ".indices tracks" | grep idx_tracks_sync`
