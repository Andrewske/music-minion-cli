---
task: 01-database-migration
status: pending
depends: []
files:
  - path: src/music_minion/core/database.py
    action: modify
---

# Database Migration v41: Genre Tables

## Context
Foundation for the genre system. Creates normalized tables for multi-genre support with priority ordering, replacing the single `tracks.genre` TEXT field while maintaining backward compatibility.

## Files to Modify/Create
- `src/music_minion/core/database.py` (modify)

## Implementation Details

### Schema Changes

Add migration to version 41 with these tables:

```sql
CREATE TABLE genres (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    emoji_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE track_genres (
    track_id INTEGER NOT NULL,
    genre_id INTEGER NOT NULL,
    position INTEGER NOT NULL DEFAULT 1,  -- 1=primary
    PRIMARY KEY (track_id, genre_id),
    FOREIGN KEY (track_id) REFERENCES tracks(id) ON DELETE CASCADE,
    FOREIGN KEY (genre_id) REFERENCES genres(id) ON DELETE CASCADE
);

CREATE INDEX idx_track_genres_track ON track_genres(track_id, position);
CREATE INDEX idx_track_genres_genre ON track_genres(genre_id);
```

### Data Migration

1. Parse existing `tracks.genre` field for all tracks with non-null genre
2. Insert unique genre names into `genres` table
3. Create `track_genres` entries with `position=1`

### Helper Functions

Add these database functions:

```python
def get_all_genres() -> list[dict]:
    """Get all genres with track_count, sorted by count desc."""

def get_track_genres(track_id: int) -> list[dict]:
    """Get ordered genres for a track (by position)."""

def set_track_genres(track_id: int, genre_ids: list[int]) -> None:
    """Replace track's genres. First in list = position 1 (primary).
    Also updates tracks.genre field for backward compat."""

def rename_genre(genre_id: int, new_name: str) -> dict:
    """Rename genre. If new_name exists, merge into existing."""

def merge_genres(source_id: int, target_id: int) -> None:
    """Merge source genre into target. Update all track_genres, delete source."""

def get_or_create_genre(name: str) -> int:
    """Get genre ID by name, or create if not exists."""
```

### Backward Compatibility

When `set_track_genres()` is called:
1. Update `track_genres` table
2. Set `tracks.genre` = name of position=1 genre
3. Write primary genre to file metadata via existing `update_track_metadata()`

## Verification

```bash
cd ~/coding/music-minion-cli
uv run music-minion  # Should auto-migrate to v41

# Verify tables created
sqlite3 ~/.config/music-minion/music-minion.db ".schema genres"
sqlite3 ~/.config/music-minion/music-minion.db ".schema track_genres"

# Verify data migrated
sqlite3 ~/.config/music-minion/music-minion.db "SELECT name, (SELECT COUNT(*) FROM track_genres WHERE genre_id = genres.id) as count FROM genres ORDER BY count DESC LIMIT 10"
```
