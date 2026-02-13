# Backend Emoji Router Implementation

## Files to Create
- `web/backend/routers/emojis.py` (new)

## Files to Modify
- `web/backend/main.py` (modify - add router registration)

## Implementation Details

### Create `web/backend/routers/emojis.py`

This file contains the complete emoji CRUD API. Key components:

**Pydantic Models:**
```python
class EmojiInfo(BaseModel):
    emoji_id: str
    type: str = 'unicode'  # 'unicode' | 'custom'
    file_path: Optional[str] = None  # Only for custom emojis
    custom_name: Optional[str]
    default_name: str
    use_count: int
    last_used: Optional[str]

class TrackEmoji(BaseModel):
    emoji_id: str
    added_at: str

class AddEmojiRequest(BaseModel):
    emoji_id: str

class UpdateEmojiMetadataRequest(BaseModel):
    custom_name: Optional[str]
```

**Pure Helper Functions (follow functional style):**
- `get_track_emojis_query(track_id, db_conn)` - Query emojis for track
- `get_top_emojis_query(db_conn, limit=50)` - Fetch top N by use_count DESC
- `get_recent_emojis_query(db_conn, limit=10)` - Fetch recently used emojis by last_used DESC
- `search_emojis_query(db_conn, query)` - Search using FTS5 MATCH
- `add_emoji_to_track_mutation(track_id, emoji, db_conn)` - Insert + increment use_count (check existence first!)
- `remove_emoji_from_track_mutation(track_id, emoji, db_conn)` - Delete (no use_count decrement)
- `update_emoji_custom_name_mutation(emoji, custom_name, db_conn)` - Update metadata

**Endpoints:**
```python
@router.get("/emojis/tracks/{track_id}/emojis")
async def get_track_emojis(track_id: int, db=Depends(get_db)) -> list[TrackEmoji]:
    """Get all emojis for a track."""
    return get_track_emojis_query(track_id, db)

@router.post("/emojis/tracks/{track_id}/emojis")
async def add_emoji_to_track(
    track_id: int,
    request: AddEmojiRequest,
    db=Depends(get_db)
) -> dict[str, bool]:
    """Add emoji to track. Returns {"added": true/false}."""
    emoji_id = normalize_emoji_id(request.emoji_id)
    added = add_emoji_to_track_mutation(track_id, emoji_id, db)
    return {"added": added}

@router.delete("/emojis/tracks/{track_id}/emojis/{emoji_id}")
async def remove_emoji_from_track(
    track_id: int,
    emoji_id: str,
    db=Depends(get_db)
) -> dict[str, bool]:
    """Remove emoji from track."""
    emoji_id = normalize_emoji_id(emoji_id)
    remove_emoji_from_track_mutation(track_id, emoji_id, db)
    return {"removed": true}

@router.get("/emojis/top")
async def get_top_emojis(limit: int = 50, db=Depends(get_db)) -> list[EmojiInfo]:
    """Get top N emojis by usage."""
    return get_top_emojis_query(db, limit)

@router.get("/emojis/recent")
async def get_recent_emojis(limit: int = 10, db=Depends(get_db)) -> list[EmojiInfo]:
    """Get recently used emojis (last N by last_used timestamp)."""
    return get_recent_emojis_query(db, limit)

@router.get("/emojis/search")
async def search_emojis(q: str, db=Depends(get_db)) -> list[EmojiInfo]:
    """Search emojis by custom or default name."""
    return search_emojis_query(db, q)

@router.get("/emojis/all")
async def get_all_emojis(
    limit: int = 100,
    offset: int = 0,
    db=Depends(get_db)
) -> list[EmojiInfo]:
    """Get all emoji metadata with pagination."""
    return get_all_emojis_query(db, limit, offset)

@router.get("/emojis/custom-picker")
async def get_custom_emojis_for_picker(db=Depends(get_db)) -> list[dict]:
    """Get custom emojis in emoji-mart format for picker component."""
    cursor = db.execute(
        """
        SELECT emoji_id, custom_name, default_name, file_path
        FROM emoji_metadata
        WHERE type = 'custom'
        ORDER BY use_count DESC
        """
    )

    return [
        {
            'id': row['emoji_id'],
            'name': row['custom_name'] or row['default_name'],
            'keywords': [row['default_name'].lower()],
            'skins': [{'src': f'/custom_emojis/{row["file_path"]}'}],
        }
        for row in cursor.fetchall()
    ]

@router.put("/emojis/metadata/{emoji_id}")
async def update_emoji_metadata(
    emoji_id: str,
    request: UpdateEmojiMetadataRequest,
    db=Depends(get_db)
) -> dict[str, bool]:
    """Update emoji custom name."""
    emoji_id = normalize_emoji_id(emoji_id)
    update_emoji_custom_name_mutation(emoji_id, request.custom_name, db)
    return {"updated": true}
```

**Note:** All endpoints normalize emoji unicode before processing to handle variation selectors consistently.

**Critical Implementation Details:**

1. **Emoji normalization:** All emoji unicode must be normalized before database operations
```python
from music_minion.core.database import normalize_emoji_unicode
import emoji

def get_emoji_default_name(emoji_unicode: str) -> str:
    """Get default name for emoji using emoji library fallback."""
    try:
        # emoji.demojize() converts emoji to :name: format
        name = emoji.demojize(emoji_unicode)
        # Remove colons and underscores, e.g., :fire: -> fire
        return name.strip(':').replace('_', ' ')
    except Exception:
        # Fallback to unicode itself if lookup fails
        return emoji_unicode
```

2. **use_count increment logic (ATOMIC):** Use UPSERT to prevent race conditions
```python
def add_emoji_to_track_mutation(track_id: int, emoji_id: str, db_conn) -> bool:
    """Add emoji to track atomically. Returns True if actually added."""
    # Normalize emoji first
    emoji_id = normalize_emoji_id(emoji_id)

    # Use IMMEDIATE transaction to prevent race conditions
    db_conn.execute("BEGIN IMMEDIATE")
    try:
        # Auto-create metadata if missing (for emojis outside initial 50)
        default_name = get_emoji_default_name(emoji_id)
        db_conn.execute(
            """
            INSERT OR IGNORE INTO emoji_metadata (emoji_id, default_name, use_count)
            VALUES (?, ?, 0)
            """,
            (emoji_id, default_name)
        )

        # Insert association (UPSERT pattern)
        cursor = db_conn.execute(
            "INSERT OR IGNORE INTO track_emojis (track_id, emoji_id) VALUES (?, ?)",
            (track_id, emoji_id)
        )

        # Only increment if row was actually inserted
        if cursor.rowcount > 0:
            db_conn.execute(
                """
                UPDATE emoji_metadata
                SET use_count = use_count + 1, last_used = CURRENT_TIMESTAMP
                WHERE emoji_id = ?
                """,
                (emoji_id,)
            )
            db_conn.commit()
            return True
        else:
            db_conn.commit()  # No-op but clean transaction
            return False
    except Exception:
        db_conn.rollback()
        raise
```

2. **Search implementation using FTS5:**
```python
def search_emojis_query(db_conn, query: str) -> list[EmojiInfo]:
    """Search emojis using Full-Text Search for scalability."""
    if not query.strip():
        return get_all_emojis_query(db_conn)

    # FTS5 MATCH syntax - searches both custom_name and default_name
    cursor = db_conn.execute(
        """
        SELECT m.emoji_id, m.type, m.file_path, m.custom_name, m.default_name, m.use_count, m.last_used
        FROM emoji_metadata_fts fts
        JOIN emoji_metadata m ON fts.rowid = m.rowid
        WHERE emoji_metadata_fts MATCH ?
        ORDER BY m.use_count DESC, m.last_used DESC
        LIMIT 100
        """,
        (query,)
    )

    return [dict(row) for row in cursor.fetchall()]
```

**Note:** FTS5 MATCH supports:
- Simple queries: `fire` matches "fire", "fireworks", "fired up"
- Phrase queries: `"red heart"` matches exact phrase
- Prefix queries: `fire*` matches "fire", "fireworks", "firecracker"
- Boolean: `fire OR energy` matches either


3. **Top 50 query:**
```python
def get_top_emojis_query(db_conn, limit: int = 50) -> list[EmojiInfo]:
    """Get top N emojis by use_count."""
    cursor = db_conn.execute(
        """
        SELECT emoji_id, type, file_path, custom_name, default_name, use_count, last_used
        FROM emoji_metadata
        ORDER BY use_count DESC, last_used DESC
        LIMIT ?
        """,
        (limit,)
    )
    return [dict(row) for row in cursor.fetchall()]
```

4. **Recent emojis query:**
```python
def get_recent_emojis_query(db_conn, limit: int = 10) -> list[EmojiInfo]:
    """Get recently used emojis (last N by timestamp)."""
    cursor = db_conn.execute(
        """
        SELECT emoji_id, type, file_path, custom_name, default_name, use_count, last_used
        FROM emoji_metadata
        WHERE last_used IS NOT NULL
        ORDER BY last_used DESC
        LIMIT ?
        """,
        (limit,)
    )
    return [dict(row) for row in cursor.fetchall()]
```

5. **All emojis query with pagination:**
```python
def get_all_emojis_query(db_conn, limit: int = 100, offset: int = 0) -> list[EmojiInfo]:
    """Get all emojis with pagination support."""
    cursor = db_conn.execute(
        """
        SELECT emoji_id, type, file_path, custom_name, default_name, use_count, last_used
        FROM emoji_metadata
        ORDER BY use_count DESC, last_used DESC
        LIMIT ? OFFSET ?
        """,
        (limit, offset)
    )
    return [dict(row) for row in cursor.fetchall()]
```

### Update `web/backend/main.py`

Add import:
```python
from .routers import emojis
```

Add router registration (near other router includes):
```python
app.include_router(emojis.router, prefix="/api", tags=["emojis"])
```

## Acceptance Criteria
- [ ] Backend starts without errors: `uv run music-minion --web`
- [ ] Test top emojis endpoint:
  ```bash
  curl http://localhost:8642/api/emojis/top?limit=10
  # Should return 10 emojis as JSON array
  ```
- [ ] Test search endpoint:
  ```bash
  curl "http://localhost:8642/api/emojis/search?q=fire"
  # Should return 🔥 and similar emojis
  ```
- [ ] Test all emojis endpoint:
  ```bash
  curl http://localhost:8642/api/emojis/all
  # Should return all 50 seeded emojis
  ```
- [ ] All functions follow pure functional style (no classes, explicit type hints)
- [ ] Functions are ≤20 lines each

## Dependencies
- Task 01 (database migration) must be complete
