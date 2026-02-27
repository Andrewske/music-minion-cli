---
task: 00-database-migration
status: pending
depends: []
files:
  - path: src/music_minion/core/database.py
    action: modify
---

# Database Migration: Add session_id to player_queue_state

## Context
The organizer playback context requires persisting the bucket session ID to survive server restarts. Currently, `player_queue_state` table only stores `context_type` and `context_id`, which is insufficient for organizer contexts that need to reference a specific bucket session.

## Current Schema

```sql
CREATE TABLE IF NOT EXISTS player_queue_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    context_type TEXT,
    context_id INTEGER,
    shuffle INTEGER,
    sort_field TEXT,
    sort_direction TEXT,
    position_in_playlist INTEGER DEFAULT 0
);
```

## Migration SQL

Add new columns:

```sql
-- Store session ID for organizer contexts
ALTER TABLE player_queue_state
ADD COLUMN context_session_id TEXT DEFAULT NULL;

-- Future-proof: metadata for bucket customization (colors, emojis, icons)
-- Not used in this implementation but cheap to add now, expensive to retrofit later
ALTER TABLE bucket_sessions
ADD COLUMN metadata TEXT DEFAULT NULL;  -- JSON stored as text
```

## Implementation Details

### 1. Update Database Schema

**File:** `src/music_minion/core/database.py`

Find the `player_queue_state` table creation and update schema version:

```python
# Update to schema version 32 (or next available)
SCHEMA_VERSION = 32

# In _migrate_database() or table creation:
cursor.execute("""
    CREATE TABLE IF NOT EXISTS player_queue_state (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        context_type TEXT,
        context_id INTEGER,
        shuffle INTEGER,
        sort_field TEXT,
        sort_direction TEXT,
        position_in_playlist INTEGER DEFAULT 0,
        context_session_id TEXT DEFAULT NULL
    )
""")

# Add migration for existing databases:
# In migration logic (check current version < 32):
cursor.execute("""
    ALTER TABLE player_queue_state
    ADD COLUMN context_session_id TEXT DEFAULT NULL
""")
```

### 2. Update save_queue_state()

**File:** `web/backend/queue_manager.py` (line ~238)

Modify INSERT to include session_id:

```python
cursor.execute(
    """
    INSERT OR REPLACE INTO player_queue_state (
        id, context_type, context_id, shuffle,
        sort_field, sort_direction, position_in_playlist, context_session_id
    ) VALUES (1, ?, ?, ?, ?, ?, ?, ?)
    """,
    (
        context.type,
        context_id,
        1 if shuffle else 0,
        sort_spec.get("field") if sort_spec else None,
        sort_spec.get("direction") if sort_spec else None,
        position_in_sorted,
        context.session_id if context.type == "organizer" else None
    ),
)
```

### 3. Update load_queue_state()

**File:** `web/backend/queue_manager.py` (line ~276)

Modify SELECT to read session_id:

```python
cursor = conn.execute(
    """
    SELECT context_type, context_id, shuffle,
           sort_field, sort_direction, position_in_playlist, context_session_id
    FROM player_queue_state
    WHERE id = 1
    """
)
```

Update return dict to include session_id:

```python
return {
    "context_type": row["context_type"],
    "context_id": row["context_id"],
    "context_session_id": row["context_session_id"],  # NEW
    "shuffle": bool(row["shuffle"]),
    "sort_spec": sort_spec,
    "position_in_sorted": row["position_in_playlist"]
}
```

### 4. Update _reconstruct_play_context()

**File:** `web/backend/queue_manager.py` (line ~703)

Remove TODO comment and implement organizer reconstruction:

```python
elif context_type == "organizer":
    # Reconstruct organizer context with session_id
    from ..queries.buckets import get_session_with_data

    # Validate session still exists and is active
    if context_session_id:
        session = get_session_with_data(context_session_id)
        if session and session["status"] == "active":
            return PlayContext(
                type="organizer",
                playlist_id=context_id,
                session_id=context_session_id,
                shuffle=shuffle
            )
        else:
            logger.warning(f"Organizer session {context_session_id} no longer active, falling back to playlist")

    # Fallback to regular playlist if session invalid
    return PlayContext(
        type="playlist",
        playlist_id=context_id,
        shuffle=shuffle
    )
```

## Rollback Plan

If migration causes issues:

```sql
-- Create new table without session_id column
CREATE TABLE player_queue_state_backup AS SELECT
    id, context_type, context_id, shuffle,
    sort_field, sort_direction, position_in_playlist
FROM player_queue_state;

-- Drop current table
DROP TABLE player_queue_state;

-- Rename backup
ALTER TABLE player_queue_state_backup RENAME TO player_queue_state;
```

## Verification

- Run migration on test database
- Verify column added: `PRAGMA table_info(player_queue_state);`
- Save organizer queue state, restart server, verify state restored
- Test with invalid session_id (deleted session) → should fallback to playlist
- Run existing queue tests: `uv run pytest web/backend/tests/test_queue_manager.py`
