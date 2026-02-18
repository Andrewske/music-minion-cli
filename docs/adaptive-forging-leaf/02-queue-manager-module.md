---
task: 02-queue-manager-module
status: done
depends: [01-database-schema]
files:
  - path: web/backend/queue_manager.py
    action: create
---

# Queue Manager Module - Pure Functional Core

## Context
Create the heart of the rolling window system: a pure functional module that handles queue initialization, dynamic refilling, rebuild on shuffle toggle, and persistence. This module has no global state and is fully testable.

## Files to Modify/Create
- web/backend/queue_manager.py (new)

## Implementation Details

### Public API Functions

Implement these functions with **pure functional design** (no global state):

#### 1. initialize_queue()
```python
def initialize_queue(
    context: PlayContext,
    db_conn,
    window_size: int = 100,
    shuffle: bool = True,
    sort_spec: Optional[dict] = None
) -> list[int]:
    """Generate initial queue of track IDs.

    Shuffle ON: Random selection
    Shuffle OFF: Sorted by track_number or sort_spec

    Returns: List of track IDs (max window_size tracks)
    """
```

**Logic:**
- Resolve context to get all available track IDs (playlist/builder/smart playlist)
- If shuffle ON: Randomly select window_size tracks
- If shuffle OFF: Sort by track_number (or sort_spec), take first window_size
- Handle playlists smaller than window_size (return all available)

#### 2. get_next_track()
```python
def get_next_track(
    context: PlayContext,
    exclusion_ids: list[int],
    db_conn,
    shuffle: bool = True,
    sort_spec: Optional[dict] = None,
    position_in_sorted: Optional[int] = None
) -> Optional[int]:
    """Pull 1 track from playlist, respecting exclusions.

    Shuffle ON: SELECT ... ORDER BY RANDOM() WHERE id NOT IN (...) LIMIT 1
    Shuffle OFF: Get next in sorted sequence

    Returns: Single track ID, or None if no tracks available
    """
```

**Logic:**
- Build exclusion WHERE clause: `WHERE id NOT IN (?, ?, ...)`
- Shuffle ON: `ORDER BY RANDOM() LIMIT 1`
- Shuffle OFF: Sort by sort_spec, skip position_in_sorted tracks, take 1
- Return None if playlist exhausted

#### 3. rebuild_queue()
```python
def rebuild_queue(
    context: PlayContext,
    current_track_id: int,
    queue: list[int],
    queue_index: int,
    db_conn,
    shuffle: bool,
    sort_spec: Optional[dict] = None
) -> list[int]:
    """Rebuild queue preserving current track and history.

    Used when toggling shuffle or changing sort.
    Keeps tracks[0:queue_index+1], rebuilds tracks[queue_index+1:]

    Returns: New complete queue (history + current + new future tracks)
    """
```

**Logic:**
- Preserve history: `queue[0:queue_index+1]` (played tracks + current)
- Build exclusion list from preserved tracks
- Generate ~99 new tracks using initialize_queue() logic
- Concatenate: `preserved + new_tracks`

#### 4. save_queue_state()
```python
def save_queue_state(
    context: PlayContext,
    queue_ids: list[int],
    queue_index: int,
    shuffle: bool,
    sort_spec: Optional[dict],
    db_conn
) -> None:
    """Persist queue state to database.

    Uses INSERT OR REPLACE for singleton pattern (id=1).
    """
```

**Logic:**
- Serialize queue_ids to JSON: `json.dumps(queue_ids)`
- Serialize sort_spec to JSON if present
- Use `INSERT OR REPLACE INTO player_queue_state (id=1, ...) VALUES (...)`
- Commit transaction

#### 5. load_queue_state()
```python
def load_queue_state(db_conn) -> Optional[dict]:
    """Restore queue state from database.

    Returns: dict with keys: queue_ids, queue_index, shuffle_enabled,
             sort_spec, context, or None if no saved state
    """
```

**Logic:**
- Query `SELECT * FROM player_queue_state WHERE id=1`
- Deserialize queue_track_ids from JSON
- Deserialize sort_spec from JSON if present
- Reconstruct PlayContext from context_type/context_id
- Return None if no row exists

### Internal Helper Functions

These are private (prefixed with `_`):

#### _get_random_track_from_playlist()
```python
def _get_random_track_from_playlist(
    context: PlayContext,
    exclusion_ids: list[int],
    db_conn
) -> Optional[int]:
    """SQL: ORDER BY RANDOM() with exclusions."""
```

#### _get_sorted_tracks_from_playlist()
```python
def _get_sorted_tracks_from_playlist(
    context: PlayContext,
    sort_spec: dict,
    limit: int,
    offset: int,
    db_conn
) -> list[int]:
    """Apply sort spec (field + direction), return track IDs."""
```

Sort field mapping with NULL handling:
- `title` → `tracks.title` (use COALESCE for empty titles: `COALESCE(tracks.title, '')`)
- `artist` → `tracks.artist` (use COALESCE: `COALESCE(tracks.artist, '')`)
- `bpm` → `tracks.bpm` (use COALESCE: `COALESCE(tracks.bpm, 120)`)
- `year` → `tracks.year` (use COALESCE: `COALESCE(tracks.year, 0)`)
- `elo_rating` → `track_ratings.elo_rating` (use COALESCE: `COALESCE(track_ratings.elo_rating, 1500)`)
- `track_number` → `tracks.track_number` (default for shuffle OFF)

**Important**: Use COALESCE to provide default values for NULL fields. This ensures consistent sort order and prevents unrated/incomplete tracks from appearing unpredictably.

#### _build_exclusion_list()
```python
def _build_exclusion_list(queue: list[int], queue_index: int) -> list[int]:
    """Extract IDs from queue[queue_index:]."""
    return queue[queue_index:]
```

#### _resolve_context_to_track_ids()
```python
def _resolve_context_to_track_ids(
    context: PlayContext,
    db_conn
) -> list[int]:
    """Handle playlist/builder/smart playlist context.

    For smart playlists: Evaluate filters dynamically.
    For manual playlists: Query playlist_tracks table.
    For builder: Query current builder tracks.
    """
```

**Reference:** See existing `resolve_queue()` in `player.py` for context resolution logic.

### Key Design Principles

1. **Pure functions**: All state passed as parameters, no global variables
2. **Explicit database connections**: Pass `db_conn`, never use global DB
3. **Type hints**: All params and returns have type annotations
4. **Error handling**: Catch SQL errors, return None/empty list on failure
5. **Logging**: Use `logger.info()` for queue operations, `logger.exception()` for errors

### Error Handling Examples

All public functions should wrap database operations in try/except blocks:

```python
def save_queue_state(...) -> None:
    """Persist queue state to database."""
    try:
        conn.execute("INSERT OR REPLACE INTO player_queue_state ...")
        conn.commit()
        logger.info(f"Saved queue state: {len(queue_ids)} tracks")
    except sqlite3.Error as e:
        logger.exception("Failed to save queue state")
        # Don't raise - persistence failing shouldn't crash playback

def get_next_track(...) -> Optional[int]:
    """Pull 1 track from playlist."""
    try:
        cursor = db_conn.execute("SELECT id FROM tracks WHERE ...")
        row = cursor.fetchone()
        return row[0] if row else None
    except sqlite3.Error as e:
        logger.exception("Error fetching next track")
        return None
```

**Defensive checks for batch operations:**

```python
# In caller (player.py)
new_track_id = get_next_track(...)
if new_track_id:
    new_tracks = batch_fetch_tracks_with_metadata([new_track_id], db)
    if new_tracks:  # Check for empty result
        _playback_state.queue.append(new_tracks[0])
    else:
        logger.warning(f"Track {new_track_id} metadata not found")
```

## Verification

```bash
# Unit tests (create these in next phase)
uv run pytest web/backend/tests/test_queue_manager.py -v

# Manual test: Import and run functions in Python REPL
uv run python
>>> from web.backend.queue_manager import initialize_queue
>>> from music_minion.core.database import get_db_connection
>>> with get_db_connection() as db:
...     queue = initialize_queue(context, db, window_size=10, shuffle=True)
...     print(f"Generated {len(queue)} tracks")
```

**Expected behavior:**
- `initialize_queue()` returns 100 unique track IDs (or less if playlist is small)
- `get_next_track()` never returns a track in exclusion_ids
- `rebuild_queue()` preserves tracks[0:queue_index+1]
- `save_queue_state()` persists to DB without error
- `load_queue_state()` round-trips correctly (save → load → identical state)
