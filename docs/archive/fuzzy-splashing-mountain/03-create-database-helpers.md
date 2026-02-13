# Create Database Helper Functions

## Files to Modify
- `src/music_minion/core/database.py` (modify)

## Implementation Details

Add helper functions for YouTube track management. The database schema already has the required columns (`youtube_id`, `local_path`, `youtube_synced_at`, `source`), so no schema changes are needed.

### Functions to Add

#### `insert_youtube_track()`
```python
def insert_youtube_track(
    local_path: str,
    youtube_id: str,
    title: str,
    artist: Optional[str],
    album: Optional[str],
    duration: float
) -> int:
    """Insert a YouTube-sourced track into database.

    Sets:
    - source = 'youtube'
    - youtube_synced_at = current timestamp
    - youtube_id = provided video ID
    - local_path = path to downloaded file

    Returns:
        Track ID of newly inserted track
    """
```

**Implementation notes**:
- Use parameterized SQL to prevent injection
- **Use Python `datetime.now()` for youtube_synced_at** (not SQL CURRENT_TIMESTAMP literal)
- Set `source` field to `'youtube'`
- Return `cursor.lastrowid` for the new track ID
- Use `get_db_connection()` context manager

#### `batch_insert_youtube_tracks()`
```python
def batch_insert_youtube_tracks(
    tracks_data: list[dict]
) -> list[int]:
    """Batch insert multiple YouTube tracks efficiently.

    Uses SQLite RETURNING clause (requires SQLite 3.35+) to get all IDs in one query.

    Args:
        tracks_data: List of dicts with keys:
            local_path, youtube_id, title, artist, album, duration

    Returns:
        List of track IDs for inserted tracks (same order as input)
    """
```

**Implementation notes**:
- Use RETURNING clause: `INSERT INTO tracks (...) VALUES (?, ?, ...) RETURNING id`
- Execute in single transaction for atomicity
- Use `datetime.now()` for all youtube_synced_at values
- If any insert fails (duplicate youtube_id), transaction rolls back

#### `get_track_by_youtube_id()`
```python
def get_track_by_youtube_id(youtube_id: str) -> Optional[Track]:
    """Check if a YouTube video is already imported.

    Args:
        youtube_id: YouTube video ID (11 characters)

    Returns:
        Track object if found, None otherwise
    """
```

**Implementation notes**:
- Query: `SELECT * FROM tracks WHERE youtube_id = ?`
- Use `db_track_to_library_track()` to convert row to Track object
- Return None if not found

#### `get_existing_youtube_ids()`
```python
def get_existing_youtube_ids(youtube_ids: list[str]) -> set[str]:
    """Batch check which YouTube IDs already exist in database.

    Args:
        youtube_ids: List of YouTube video IDs to check

    Returns:
        Set of youtube_ids that already exist
    """
```

**Implementation notes**:
- Query: `SELECT youtube_id FROM tracks WHERE youtube_id IN (?, ?, ...)`
- Build parameterized query dynamically based on list length
- Return set for O(1) lookup by caller

### Existing Schema Reference

The `tracks` table already has these columns:
- `youtube_id TEXT` (with unique index)
- `local_path TEXT`
- `youtube_synced_at TIMESTAMP`
- `source TEXT`

No schema migrations needed.

## Acceptance Criteria

- [ ] `insert_youtube_track()` successfully inserts tracks with all required fields
- [ ] Track source is set to 'youtube'
- [ ] `youtube_synced_at` uses Python `datetime.now()` (not SQL literal)
- [ ] Function returns the new track ID
- [ ] `batch_insert_youtube_tracks()` uses RETURNING clause for efficiency
- [ ] Batch insert is atomic (all-or-nothing transaction)
- [ ] `get_track_by_youtube_id()` finds existing tracks by youtube_id
- [ ] `get_existing_youtube_ids()` batch checks multiple IDs efficiently
- [ ] Returns None/empty when youtube_id doesn't exist
- [ ] All functions use parameterized queries (SQL injection safe)

## Dependencies

None - database schema already supports YouTube tracks.
