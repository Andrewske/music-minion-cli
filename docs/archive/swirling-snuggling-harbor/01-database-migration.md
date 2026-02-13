# Database Migration - v26 to v27

## Files to Modify
- `src/music_minion/core/database.py` (modify)

## Implementation Details

Add database schema version 27 migration to support playlist builder functionality.

### Changes Required

1. **Update Schema Version**
   - Change `SCHEMA_VERSION = 26` to `SCHEMA_VERSION = 27`

2. **Add Migration Block**
   Add the following migration block in the `migrate_database()` function:

```python
if current_version < 27:
    # Migration from v26 to v27: Add playlist builder tables

    # Playlist builder filters (separate from smart playlist filters)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS playlist_builder_filters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            playlist_id INTEGER NOT NULL,
            field TEXT NOT NULL,
            operator TEXT NOT NULL,
            value TEXT NOT NULL,
            conjunction TEXT NOT NULL DEFAULT 'AND',
            FOREIGN KEY (playlist_id) REFERENCES playlists (id) ON DELETE CASCADE
        )
    """)
    conn.execute("""
        CREATE INDEX idx_builder_filters_playlist
        ON playlist_builder_filters(playlist_id)
    """)

    # Permanently skipped tracks per playlist
    conn.execute("""
        CREATE TABLE IF NOT EXISTS playlist_builder_skipped (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            playlist_id INTEGER NOT NULL,
            track_id INTEGER NOT NULL,
            skipped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (playlist_id) REFERENCES playlists (id) ON DELETE CASCADE,
            FOREIGN KEY (track_id) REFERENCES tracks (id) ON DELETE CASCADE,
            UNIQUE (playlist_id, track_id)
        )
    """)
    conn.execute("""
        CREATE INDEX idx_builder_skipped_playlist
        ON playlist_builder_skipped(playlist_id)
    """)
    conn.execute("""
        CREATE INDEX idx_builder_skipped_track
        ON playlist_builder_skipped(track_id)
    """)

    # Active builder sessions
    conn.execute("""
        CREATE TABLE IF NOT EXISTS playlist_builder_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            playlist_id INTEGER UNIQUE NOT NULL,
            last_processed_track_id INTEGER,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (playlist_id) REFERENCES playlists (id) ON DELETE CASCADE,
            FOREIGN KEY (last_processed_track_id) REFERENCES tracks (id) ON DELETE SET NULL
        )
    """)

    conn.commit()
```

## Acceptance Criteria

1. Database schema version incremented to 27
2. Three new tables created with proper foreign keys:
   - `playlist_builder_filters`
   - `playlist_builder_skipped`
   - `playlist_builder_sessions`
3. All indexes created successfully
4. Existing database migrates without errors
5. Test by running: `uv run music-minion` (should auto-migrate on startup)

## Dependencies
- None (foundational task)

## Verification Steps

```bash
# Start the application (triggers migration)
uv run music-minion

# Check database schema in SQLite
sqlite3 ~/.local/share/music-minion/music_minion.db ".schema playlist_builder_filters"
sqlite3 ~/.local/share/music-minion/music_minion.db ".schema playlist_builder_skipped"
sqlite3 ~/.local/share/music-minion/music_minion.db ".schema playlist_builder_sessions"
```
