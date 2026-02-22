---
task: 01-database-migration
status: done
depends: []
files:
  - path: src/music_minion/core/database.py
    action: modify
---

# Database Migration: track_emojis + Bucket Tables

## Context
Enable duplicate emojis per track with source tracking, and create bucket session infrastructure for playlist organization.

## Files to Modify/Create
- src/music_minion/core/database.py (modify)

## Implementation Details

### 1. Modify `track_emojis` to allow duplicates

Current: Composite PK `(track_id, emoji_id)` prevents duplicates
New: Add surrogate key + source tracking

```sql
-- Migration: Add instance tracking
-- SQLite doesn't support DROP CONSTRAINT, need table rebuild
CREATE TABLE track_emojis_new (
    id TEXT PRIMARY KEY,
    track_id INTEGER NOT NULL,
    emoji_id TEXT NOT NULL,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    source_type TEXT DEFAULT 'manual',  -- 'manual' | 'bucket' | 'bulk'
    source_id TEXT,  -- bucket_id if source_type='bucket'
    FOREIGN KEY (track_id) REFERENCES tracks (id) ON DELETE CASCADE
);

-- Backfill existing rows with UUIDs (32-char hex, no hyphens - consistent with SQLite pattern)
-- Note: Using hex format rather than standard UUID for simplicity; functionally equivalent
INSERT INTO track_emojis_new (id, track_id, emoji_id, added_at, source_type, source_id)
SELECT lower(hex(randomblob(16))), track_id, emoji_id, added_at, 'manual', NULL FROM track_emojis;

DROP TABLE track_emojis;
ALTER TABLE track_emojis_new RENAME TO track_emojis;
CREATE INDEX idx_track_emojis_track_id ON track_emojis(track_id);
CREATE INDEX idx_track_emojis_emoji_id ON track_emojis(emoji_id);
CREATE INDEX idx_track_emojis_source ON track_emojis(source_type, source_id);
```

### 2. New tables for bucket sessions

```sql
CREATE TABLE bucket_sessions (
    id TEXT PRIMARY KEY,  -- UUID
    playlist_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'active',  -- 'active' | 'applied' | 'discarded'
    FOREIGN KEY (playlist_id) REFERENCES playlists (id) ON DELETE CASCADE
);

-- Enforce single active session per playlist (idempotent get-or-create pattern)
CREATE UNIQUE INDEX idx_active_session_playlist
ON bucket_sessions(playlist_id)
WHERE status = 'active';

CREATE TABLE buckets (
    id TEXT PRIMARY KEY,  -- UUID
    session_id TEXT NOT NULL,
    name TEXT NOT NULL,
    emoji_id TEXT,  -- NULL or emoji to auto-add
    position INTEGER NOT NULL,  -- order of bucket
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES bucket_sessions (id) ON DELETE CASCADE
);

CREATE TABLE bucket_tracks (
    id TEXT PRIMARY KEY,  -- UUID
    bucket_id TEXT NOT NULL,
    track_id INTEGER NOT NULL,
    position INTEGER NOT NULL,  -- order within bucket
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (bucket_id) REFERENCES buckets (id) ON DELETE CASCADE,
    FOREIGN KEY (track_id) REFERENCES tracks (id) ON DELETE CASCADE,
    UNIQUE (bucket_id, track_id)  -- track can only be in one bucket per session
);

CREATE INDEX idx_bucket_tracks_bucket_id ON bucket_tracks(bucket_id);
CREATE INDEX idx_bucket_tracks_track_id ON bucket_tracks(track_id);
```

### Migration implementation
- Increment SCHEMA_VERSION
- Add migration function in the existing migration chain
- Handle table rebuild for track_emojis carefully (preserve data)

## Verification
```bash
# Run the app to trigger migration
uv run music-minion --web

# Check tables exist in SQLite
sqlite3 ~/.local/share/music-minion/music_minion.db ".schema track_emojis"
sqlite3 ~/.local/share/music-minion/music_minion.db ".schema bucket_sessions"
sqlite3 ~/.local/share/music-minion/music_minion.db ".schema buckets"
sqlite3 ~/.local/share/music-minion/music_minion.db ".schema bucket_tracks"

# Verify existing emojis were migrated with UUIDs
sqlite3 ~/.local/share/music-minion/music_minion.db "SELECT id, track_id, emoji_id, source_type FROM track_emojis LIMIT 5"
```
