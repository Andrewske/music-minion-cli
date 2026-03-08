---
task: 01-database-migration
status: pending
depends: []
files:
  - path: src/music_minion/core/database.py
    action: modify
---

# Database Migration: bucket_playlist_links Table

## Context
Foundation for bucket-to-playlist linking. Creates the new table that stores which bucket is linked to which playlist. Must be done first as all other tasks depend on this schema.

## Files to Modify/Create
- src/music_minion/core/database.py (modify)

## Implementation Details

Add migration v41 (or next available version) with:

```sql
CREATE TABLE IF NOT EXISTS bucket_playlist_links (
    id TEXT PRIMARY KEY,
    bucket_id TEXT NOT NULL UNIQUE,  -- One link per bucket
    playlist_id INTEGER NOT NULL,
    link_type TEXT DEFAULT 'sync',  -- Future: 'sync', 'mirror', 'one-way'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (bucket_id) REFERENCES buckets (id) ON DELETE CASCADE,
    FOREIGN KEY (playlist_id) REFERENCES playlists (id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_bucket_playlist_links_bucket ON bucket_playlist_links(bucket_id);
CREATE INDEX IF NOT EXISTS idx_bucket_playlist_links_playlist ON bucket_playlist_links(playlist_id);
```

Key design decisions:
- `UNIQUE` on `bucket_id`: One bucket can only link to one playlist
- `ON DELETE CASCADE` for bucket: When bucket deleted, link removed
- `ON DELETE CASCADE` for playlist: When playlist deleted, link row removed (bucket becomes unlinked)
- `link_type` column: Reserved for future sync modes (currently unused, defaults to 'sync')

## Verification

1. Run the app to trigger migration: `uv run music-minion --dev`
2. Verify table exists:
   ```bash
   sqlite3 ~/.local/share/music-minion/music_minion.db ".schema bucket_playlist_links"
   ```
3. Verify indexes exist:
   ```bash
   sqlite3 ~/.local/share/music-minion/music_minion.db ".indexes bucket_playlist_links"
   ```
