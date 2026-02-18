---
task: 01-database-schema
status: pending
depends: []
files:
  - path: src/music_minion/core/database.py
    action: modify
---

# Database Schema - Player Queue State

## Context
Add persistence layer for the rolling window queue. This foundational change enables queue state to survive server restarts and provides storage for shuffle/sort state.

## Files to Modify/Create
- src/music_minion/core/database.py (modify)

## Implementation Details

### Add player_queue_state Table

Add this table definition to the schema:

```sql
CREATE TABLE IF NOT EXISTS player_queue_state (
    id INTEGER PRIMARY KEY CHECK (id = 1), -- Singleton pattern
    context_type TEXT NOT NULL, -- 'playlist', 'builder', 'comparison', etc.
    context_id INTEGER, -- playlist_id, builder_id, etc.
    shuffle_enabled BOOLEAN NOT NULL,
    sort_field TEXT, -- NULL if shuffle, else 'bpm', 'title', etc.
    sort_direction TEXT, -- 'asc' or 'desc'
    queue_track_ids TEXT NOT NULL, -- JSON array: "[123, 456, 789]"
    queue_index INTEGER NOT NULL,
    position_in_sorted INTEGER, -- For shuffle OFF mode tracking
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

**Key Design:**
- **Singleton pattern**: Only one row (id=1) for single-user system
- **JSON array**: Store track IDs as JSON text for simplicity
- **Context tracking**: Stores what playlist/builder the queue came from
- **Sort state**: Tracks manual sort field + direction

### Add Schema Upgrade Function

**Step 1: Update SCHEMA_VERSION constant**

In `database.py`, change:
```python
SCHEMA_VERSION = 33  # Current version
```
To:
```python
SCHEMA_VERSION = 34  # Add player_queue_state table
```

**Step 2: Add migration to migrate_database() function**

Add this block to the `migrate_database()` function:

```python
if current_version < 34:
    logger.info("Migrating to v34: Add player_queue_state table")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS player_queue_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            context_type TEXT NOT NULL,
            context_id INTEGER,
            shuffle_enabled BOOLEAN NOT NULL,
            sort_field TEXT,
            sort_direction TEXT,
            queue_track_ids TEXT NOT NULL,
            queue_index INTEGER NOT NULL,
            position_in_playlist INTEGER,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
```

**Note**: Renamed `position_in_sorted` to `position_in_playlist` for clarity (tracks position in global playlist during sorted/sequential playback).

## Verification

```bash
# Start the app
uv run music-minion --web

# Check schema was applied
sqlite3 ~/.local/share/music-minion/library.db "SELECT sql FROM sqlite_master WHERE name='player_queue_state';"

# Should show the CREATE TABLE statement
```

**Expected output:**
- Table exists with all columns
- id constraint enforces singleton (only one row allowed)
- No errors in logs during startup
