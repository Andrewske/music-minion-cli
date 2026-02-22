---
task: 02-emoji-source-type-updates
status: pending
depends: [01-database-migration]
files:
  - path: web/backend/queries/emojis.py
    action: modify
  - path: web/backend/routers/emojis.py
    action: modify
  - path: scripts/bulk-tag-emoji.py
    action: modify
---

# Update Emoji Operations with source_type

## Context
Now that track_emojis supports source tracking, all emoji addition points need to pass `source_type` and optionally `source_id`.

## Files to Modify/Create
- web/backend/queries/emojis.py (modify)
- web/backend/routers/emojis.py (modify)
- scripts/bulk-tag-emoji.py (modify)

## Implementation Details

### 1. Update `add_emoji_to_track_mutation` in queries/emojis.py

Add parameters:
- `source_type: str = 'manual'`
- `source_id: str | None = None`

Update INSERT to include new columns:
```python
def add_emoji_to_track_mutation(
    conn: sqlite3.Connection,
    track_id: int,
    emoji_id: str,
    source_type: str = 'manual',
    source_id: str | None = None
) -> bool:
    # Generate UUID for new instance
    instance_id = str(uuid.uuid4())

    cursor = conn.execute(
        """
        INSERT INTO track_emojis (id, track_id, emoji_id, source_type, source_id)
        VALUES (?, ?, ?, ?, ?)
        """,
        (instance_id, track_id, normalize_emoji_id(emoji_id), source_type, source_id)
    )
    # ... rest of function
```

### 2. Update `remove_emoji_from_track_mutation`

Add optional `source_id` parameter for targeted removal. **Protected emojis** (bucket/playlist) cannot be deleted directly - must remove track from bucket/playlist instead:
```python
def remove_emoji_from_track_mutation(
    conn: sqlite3.Connection,
    track_id: int,
    emoji_id: str,
    source_id: str | None = None,
    force: bool = False  # Only True when removing from bucket/playlist
) -> dict:
    """
    Returns: {"success": bool, "protected": bool, "source_type": str | None, "source_id": str | None}
    """
    normalized = normalize_emoji_id(emoji_id)

    if source_id:
        # Remove specific instance by source (used by bucket/playlist removal)
        conn.execute(
            "DELETE FROM track_emojis WHERE track_id = ? AND emoji_id = ? AND source_id = ?",
            (track_id, normalized, source_id)
        )
        return {"success": True, "protected": False}

    # Check if this emoji is protected (from bucket or playlist)
    cursor = conn.execute(
        """SELECT id, source_type, source_id FROM track_emojis
           WHERE track_id = ? AND emoji_id = ? AND source_type IN ('bucket', 'playlist')
           LIMIT 1""",
        (track_id, normalized)
    )
    protected_row = cursor.fetchone()

    if protected_row and not force:
        # Return info about the protected emoji for UI to show warning
        return {
            "success": False,
            "protected": True,
            "source_type": protected_row[1],
            "source_id": protected_row[2]
        }

    # Remove one manual instance
    conn.execute(
        """DELETE FROM track_emojis WHERE id = (
            SELECT id FROM track_emojis
            WHERE track_id = ? AND emoji_id = ? AND source_type = 'manual'
            LIMIT 1
        )""",
        (track_id, normalized)
    )
    return {"success": True, "protected": False}
```

### 2b. Add helper to get emoji display order

Emojis display in priority: playlist → bucket → manual
```python
def get_track_emojis_ordered(conn: sqlite3.Connection, track_id: int) -> list[dict]:
    """Return emojis for track, ordered by source priority."""
    cursor = conn.execute(
        """SELECT id, emoji_id, source_type, source_id, added_at
           FROM track_emojis
           WHERE track_id = ?
           ORDER BY
             CASE source_type
               WHEN 'playlist' THEN 0
               WHEN 'bucket' THEN 1
               ELSE 2
             END,
             added_at DESC""",
        (track_id,)
    )
    return [
        {"id": r[0], "emoji_id": r[1], "source_type": r[2], "source_id": r[3], "added_at": r[4]}
        for r in cursor.fetchall()
    ]
```

### 3. Update routers/emojis.py POST endpoint

Pass `source_type='manual'` to mutation:
```python
@router.post("/tracks/{track_id}/emojis")
async def add_emoji_to_track(track_id: int, body: AddEmojiBody):
    with get_db_connection() as conn:
        added = add_emoji_to_track_mutation(
            conn, track_id, body.emoji_id, source_type='manual'
        )
```

### 4. Update scripts/bulk-tag-emoji.py

Pass `source_type='bulk'` when adding emojis:
```python
add_emoji_to_track_mutation(conn, track_id, emoji_id, source_type='bulk')
```

## Verification
```bash
# Test manual emoji add via API
curl -X POST http://localhost:8642/api/emojis/tracks/1/emojis \
  -H "Content-Type: application/json" \
  -d '{"emoji_id": "🔥"}'

# Check source_type was set
sqlite3 ~/.local/share/music-minion/music_minion.db \
  "SELECT id, emoji_id, source_type FROM track_emojis WHERE track_id = 1 ORDER BY added_at DESC LIMIT 1"

# Test bulk tagging
uv run scripts/bulk-tag-emoji.py --track-ids 1,2 --emoji "⭐"

# Verify bulk source_type
sqlite3 ~/.local/share/music-minion/music_minion.db \
  "SELECT id, track_id, emoji_id, source_type FROM track_emojis WHERE source_type = 'bulk'"
```
