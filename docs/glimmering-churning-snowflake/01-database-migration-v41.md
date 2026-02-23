---
task: 01-database-migration-v41
status: done
depends: []
files:
  - path: src/music_minion/core/database.py
    action: modify
---

# Database Migration v41: Genre Tables & Triggers

## Context
Foundation for multi-genre support. Creates normalized genre storage with automatic sync to `tracks.genre` for file metadata compatibility.

## Files to Modify/Create
- `src/music_minion/core/database.py` (modify)

## Implementation Details

### 1. Add `normalize_genre_name()` function
Place near `normalize_emoji_id()` (around line 84):
```python
def normalize_genre_name(genre: str) -> str:
    """Normalize genre name for consistent storage and matching."""
    return unicodedata.normalize("NFC", genre.strip().lower())
```

### 2. Add v41 migration block
After the v40 migration section, add:

```sql
CREATE TABLE genres (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    emoji_id TEXT,
    track_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE track_genres (
    track_id INTEGER NOT NULL,
    genre_id INTEGER NOT NULL,
    position INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (track_id, genre_id),
    FOREIGN KEY (track_id) REFERENCES tracks(id) ON DELETE CASCADE,
    FOREIGN KEY (genre_id) REFERENCES genres(id) ON DELETE RESTRICT
);

CREATE INDEX idx_track_genres_track ON track_genres(track_id, position);
CREATE INDEX idx_track_genres_genre ON track_genres(genre_id);
```

### 3. Add sync triggers
```sql
-- Trigger: sync tracks.genre from track_genres position=1
CREATE TRIGGER sync_primary_genre_insert AFTER INSERT ON track_genres
WHEN NEW.position = 1
BEGIN
    UPDATE tracks SET genre = (SELECT name FROM genres WHERE id = NEW.genre_id)
    WHERE id = NEW.track_id;
END;

CREATE TRIGGER sync_primary_genre_update AFTER UPDATE ON track_genres
WHEN NEW.position = 1 OR OLD.position = 1
BEGIN
    UPDATE tracks SET genre = (
        SELECT g.name FROM genres g
        JOIN track_genres tg ON g.id = tg.genre_id
        WHERE tg.track_id = NEW.track_id AND tg.position = 1
    ) WHERE id = NEW.track_id;
END;

CREATE TRIGGER sync_primary_genre_delete AFTER DELETE ON track_genres
WHEN OLD.position = 1
BEGIN
    UPDATE tracks SET genre = (
        SELECT g.name FROM genres g
        JOIN track_genres tg ON g.id = tg.genre_id
        WHERE tg.track_id = OLD.track_id AND tg.position = 1
    ) WHERE id = OLD.track_id;
END;
```

### 4. Add track_count triggers
```sql
CREATE TRIGGER update_genre_count_insert AFTER INSERT ON track_genres
BEGIN
    UPDATE genres SET track_count = track_count + 1 WHERE id = NEW.genre_id;
END;

CREATE TRIGGER update_genre_count_delete AFTER DELETE ON track_genres
BEGIN
    UPDATE genres SET track_count = track_count - 1 WHERE id = OLD.genre_id;
END;
```

### 5. Migrate existing data
```python
# Get unique normalized genres from tracks
rows = conn.execute("SELECT DISTINCT genre FROM tracks WHERE genre IS NOT NULL AND genre != ''").fetchall()
for (genre,) in rows:
    normalized = normalize_genre_name(genre)
    conn.execute("INSERT OR IGNORE INTO genres (name) VALUES (?)", (normalized,))

# Populate track_genres from tracks.genre
conn.execute("""
    INSERT INTO track_genres (track_id, genre_id, position)
    SELECT t.id, g.id, 1
    FROM tracks t
    JOIN genres g ON g.name = ?
    WHERE t.genre IS NOT NULL AND t.genre != ''
""")
# Note: Need to normalize each track's genre during migration
```

### 6. Update version
```python
conn.execute("INSERT OR REPLACE INTO schema_version (id, version) VALUES (1, 41)")
```

## Verification
```bash
cd ~/coding/music-minion-cli
uv run music-minion  # Should auto-migrate
sqlite3 ~/.config/music-minion/music-minion.db ".schema genres"
sqlite3 ~/.config/music-minion/music-minion.db ".schema track_genres"
sqlite3 ~/.config/music-minion/music-minion.db "SELECT sql FROM sqlite_master WHERE type='trigger' AND name LIKE '%genre%'"
```
