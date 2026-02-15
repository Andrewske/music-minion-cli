# Database Schema Migration (v30 → v31)

## Files to Modify
- `src/music_minion/core/database.py` (modify)

## Implementation Details

### Update Schema Version
Change `SCHEMA_VERSION = 31` at the top of database.py

### Add Migration v30 → v31
Add the following migration block to the `migrate_database()` function:

```python
if current_version < 31:
    logger.info("Migrating to v31: Adding emoji reaction tables")

    # Track-emoji associations (many-to-many)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS track_emojis (
            track_id INTEGER NOT NULL,
            emoji_id TEXT NOT NULL,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (track_id, emoji_id),
            FOREIGN KEY (track_id) REFERENCES tracks (id) ON DELETE CASCADE
        )
    """)

    # Emoji metadata (usage stats + custom names + custom emoji support)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS emoji_metadata (
            emoji_id TEXT PRIMARY KEY,
            type TEXT NOT NULL DEFAULT 'unicode',
            file_path TEXT,
            custom_name TEXT,
            default_name TEXT NOT NULL,
            use_count INTEGER DEFAULT 0,
            last_used TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create custom_emojis directory for uploaded images
    custom_emojis_dir = get_data_dir() / "custom_emojis"
    custom_emojis_dir.mkdir(exist_ok=True)

    # Performance indexes
    conn.execute("CREATE INDEX idx_track_emojis_track_id ON track_emojis(track_id)")
    conn.execute("CREATE INDEX idx_track_emojis_emoji_id ON track_emojis(emoji_id)")  # For emoji filtering

    # Regular indexes for sorting
    conn.execute("CREATE INDEX idx_emoji_metadata_use_count ON emoji_metadata(use_count DESC, last_used DESC)")

    # Full-Text Search index for searching emoji names (supports ALL emojis, not just initial 50)
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS emoji_metadata_fts USING fts5(
            emoji_id UNINDEXED,
            custom_name,
            default_name,
            content=emoji_metadata,
            content_rowid=rowid
        )
    """)

    # Triggers to keep FTS index in sync with emoji_metadata
    conn.execute("""
        CREATE TRIGGER emoji_metadata_fts_insert AFTER INSERT ON emoji_metadata BEGIN
            INSERT INTO emoji_metadata_fts(rowid, emoji_id, custom_name, default_name)
            VALUES (new.rowid, new.emoji_id, new.custom_name, new.default_name);
        END
    """)

    conn.execute("""
        CREATE TRIGGER emoji_metadata_fts_update AFTER UPDATE ON emoji_metadata BEGIN
            UPDATE emoji_metadata_fts
            SET custom_name = new.custom_name, default_name = new.default_name
            WHERE rowid = new.rowid;
        END
    """)

    conn.execute("""
        CREATE TRIGGER emoji_metadata_fts_delete AFTER DELETE ON emoji_metadata BEGIN
            DELETE FROM emoji_metadata_fts WHERE rowid = old.rowid;
        END
    """)

    conn.commit()
```

### Add Emoji Seeding Function
Add this constant and function near the top of database.py (after imports):

```python
import emoji  # NEW: pip install emoji (uv add emoji)

INITIAL_TOP_50_EMOJIS = [
    # Energy/Vibe (8)
    ("🔥", "fire"), ("⚡", "high voltage"), ("💥", "collision"),
    ("✨", "sparkles"), ("🌟", "star"), ("💫", "dizzy"),
    ("🎆", "fireworks"), ("🌈", "rainbow"),

    # Emotions (10)
    ("💪", "flexed biceps"), ("🎯", "direct hit"), ("😍", "smiling face with heart-eyes"),
    ("😎", "smiling face with sunglasses"), ("🤘", "sign of the horns"),
    ("👌", "ok hand"), ("🙌", "raising hands"), ("💖", "sparkling heart"),
    ("❤️", "red heart"), ("💯", "hundred points"),

    # Music/Audio (8)
    ("🎵", "musical note"), ("🎶", "musical notes"), ("🎤", "microphone"),
    ("🎧", "headphone"), ("🔊", "speaker high volume"), ("🎸", "guitar"),
    ("🎹", "musical keyboard"), ("🥁", "drum"),

    # Dance/Movement (6)
    ("💃", "woman dancing"), ("🕺", "man dancing"), ("🪩", "mirror ball"),
    ("🎉", "party popper"), ("🎊", "confetti ball"), ("🏃", "person running"),

    # Chill/Relaxed (6)
    ("😌", "relieved face"), ("🌙", "crescent moon"), ("☁️", "cloud"),
    ("🌊", "water wave"), ("🍃", "leaf fluttering in wind"), ("🧘", "person in lotus position"),

    # Miscellaneous (12)
    ("🚀", "rocket"), ("💎", "gem stone"), ("👑", "crown"),
    ("🌺", "hibiscus"), ("🔮", "crystal ball"), ("⭐", "star"),
    ("🌸", "cherry blossom"), ("🦋", "butterfly"), ("🐉", "dragon"),
    ("🎭", "performing arts"), ("🏆", "trophy"), ("🎨", "artist palette")
]

def seed_initial_emojis(conn) -> None:
    """Seed emoji_metadata with curated top 50 music-relevant emojis."""
    conn.executemany(
        """
        INSERT OR IGNORE INTO emoji_metadata (emoji_id, default_name, use_count)
        VALUES (?, ?, 0)
        """,
        INITIAL_TOP_50_EMOJIS
    )
    conn.commit()

    # Verify FTS index was populated by triggers
    cursor = conn.execute("SELECT COUNT(*) FROM emoji_metadata_fts")
    fts_count = cursor.fetchone()[0]
    if fts_count != 50:
        logger.error(f"FTS index not properly populated. Expected 50, got {fts_count}")
        logger.info("Run this to rebuild: INSERT INTO emoji_metadata_fts SELECT rowid, emoji_id, custom_name, default_name FROM emoji_metadata")

def normalize_emoji_id(emoji_str: str) -> str:
    """Normalize emoji ID to consistent form.

    For Unicode emojis: Normalizes to NFC form, strips variation selectors.
    For custom emojis (UUIDs): Returns unchanged.

    Args:
        emoji_str: Either Unicode emoji character or UUID for custom emoji

    Returns:
        Normalized emoji identifier
    """
    import unicodedata

    # UUID pattern check for custom emojis (they don't need normalization)
    if len(emoji_str) == 36 and emoji_str.count('-') == 4:
        return emoji_str

    # Strip variation selectors (VS15 text, VS16 emoji presentation)
    emoji_str = emoji_str.replace('\ufe0e', '').replace('\ufe0f', '')

    # Normalize Unicode emojis to NFC form
    return unicodedata.normalize('NFC', emoji_str)
```

### Call Seeding Function
At the end of the v31 migration block (inside the `if current_version < 31:` block), call:

```python
    seed_initial_emojis(conn)
```

## Acceptance Criteria
- [ ] Run `uv run music-minion --dev` without errors
- [ ] Verify migration runs: Check logs for "Migrating to v31: Adding emoji reaction tables"
- [ ] Database schema version is 31:
  ```bash
  sqlite3 ~/.local/share/music-minion/music_minion.db "SELECT * FROM schema_version"
  ```
- [ ] 50 emojis seeded:
  ```bash
  sqlite3 ~/.local/share/music-minion/music_minion.db "SELECT COUNT(*) FROM emoji_metadata"
  # Should return 50
  ```
- [ ] Tables exist:
  ```bash
  sqlite3 ~/.local/share/music-minion/music_minion.db ".tables"
  # Should show track_emojis, emoji_metadata, and emoji_metadata_fts
  ```
- [ ] FTS index is populated:
  ```bash
  sqlite3 ~/.local/share/music-minion/music_minion.db "SELECT COUNT(*) FROM emoji_metadata_fts"
  # Should return 50 (same as emoji_metadata)
  ```
- [ ] Triggers exist:
  ```bash
  sqlite3 ~/.local/share/music-minion/music_minion.db ".schema emoji_metadata_fts_insert"
  # Should show trigger definition
  ```

## Dependencies
None - this is the foundation task
