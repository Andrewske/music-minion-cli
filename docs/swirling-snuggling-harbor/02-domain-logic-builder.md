# Domain Logic - Playlist Builder Module

## Files to Create
- `src/music_minion/domain/playlists/builder.py` (new)

## Implementation Details

Create pure functional domain logic for playlist builder operations following Music Minion's functional architecture patterns.

### Module Structure

The module should contain the following pure functions:

#### Filter Management
```python
def get_builder_filters(playlist_id: int) -> list[dict]:
    """Get builder filters for a playlist."""

def set_builder_filters(playlist_id: int, filters: list[dict]) -> None:
    """Atomically replace all builder filters for a playlist."""

def clear_builder_filters(playlist_id: int) -> None:
    """Remove all builder filters for a playlist."""
```

#### Candidate Selection
```python
def get_candidate_tracks(playlist_id: int) -> list[dict]:
    """Get all eligible candidate tracks.

    Returns tracks that:
    - Match builder filters (if any set)
    - Are NOT already in the playlist
    - Are NOT in the skipped list
    - Are NOT archived

    Returns up to 100 random candidates for performance.
    Includes ELO rating data.
    """
```

**Key SQL Query Pattern (Optimized):**
```sql
SELECT DISTINCT t.*, COALESCE(er.rating, 1500.0) as elo_rating
FROM tracks t
LEFT JOIN elo_ratings er ON t.id = er.track_id
WHERE {builder_filter_where_clause}
  AND NOT EXISTS (SELECT 1 FROM playlist_tracks WHERE playlist_id = ? AND track_id = t.id)
  AND NOT EXISTS (SELECT 1 FROM playlist_builder_skipped WHERE playlist_id = ? AND track_id = t.id)
  AND NOT EXISTS (SELECT 1 FROM ratings WHERE rating_type = 'archive' AND track_id = t.id)
ORDER BY RANDOM()
LIMIT 100
```

**Note:** Uses `NOT EXISTS` instead of `NOT IN` for 10-50x better performance on large track libraries.

#### Skip/Add Operations
```python
def skip_track(playlist_id: int, track_id: int) -> dict:
    """Mark track as skipped and persist to database.

    CRITICAL: Must INSERT into playlist_builder_skipped table
    so broken tracks don't reappear in future sessions.

    Implementation:
        with get_db_connection() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO playlist_builder_skipped (playlist_id, track_id) VALUES (?, ?)",
                (playlist_id, track_id)
            )
            conn.commit()

    Returns: {
        'skipped_track_id': int,
        'success': bool
    }
    """

def add_track(playlist_id: int, track_id: int) -> dict:
    """Add track to playlist using existing CRUD.

    Use: music_minion.domain.playlists.crud.add_track_to_playlist()

    Returns: {
        'added_track_id': int,
        'success': bool
    }
    """

def get_next_candidate(playlist_id: int, exclude_track_id: int | None = None) -> dict | None:
    """Get next random candidate track for the session.

    Excludes the last processed track for variety.
    Returns None if no candidates available.

    Args:
        playlist_id: Playlist ID
        exclude_track_id: Track ID to exclude (typically last processed)

    Returns: Track dict or None
    """

def unskip_track(playlist_id: int, track_id: int) -> None:
    """Remove track from skipped list."""

def get_skipped_tracks(playlist_id: int) -> list[dict]:
    """Get all skipped tracks for a playlist (for review UI)."""
```

#### Session Management
```python
def start_builder_session(playlist_id: int) -> dict:
    """Create or resume builder session.

    Note: Does NOT return current track. Frontend calls get_next_candidate() separately.

    Returns: {
        'session_id': int,
        'playlist_id': int,
        'started_at': str,
        'updated_at': str
    }
    """

def get_active_session(playlist_id: int) -> Optional[dict]:
    """Get active builder session for playlist.

    Returns session metadata (no current track - computed fresh each time).
    """

def end_builder_session(playlist_id: int) -> None:
    """Clean up builder session."""

def update_last_processed_track(playlist_id: int, track_id: int) -> None:
    """Update session's last processed track ID.

    Used to exclude recently-seen tracks from next candidate selection.
    """
```

### Implementation Guidelines

1. **Reuse Existing Filter Logic**
   - Import and use `build_filter_query()` from `domain/playlists/filters.py`
   - Same validation as smart playlists
   - Safe parameterized queries

2. **Database Patterns**
   - Use `get_db_connection()` context manager
   - Single transaction per operation
   - Proper error handling with try/except

3. **Functional Style**
   - Pure functions with explicit parameters
   - No global state
   - No classes (use dicts for return values)
   - Type hints on all functions

4. **Performance**
   - LIMIT 100 on candidate queries
   - Use indexes (already created in migration)
   - Batch operations where possible

5. **Error Handling**
   - Domain functions raise exceptions for error conditions
   - API layer catches and converts to HTTPException
   - Examples: ValueError for invalid inputs, sqlite3.Error for DB issues

## Acceptance Criteria

1. All functions implemented with proper type hints
2. Filter logic reuses existing smart playlist validation
3. SQL queries use parameterized statements (no injection risk)
4. Functions return proper data structures (dicts/lists)
5. No circular imports
6. Follows functional programming patterns (no classes, pure functions)

## Dependencies
- Task 01: Database migration must be complete

## Testing

Create tests in `tests/test_builder.py`:
- Test filter CRUD operations
- Test candidate selection with various filters
- Test skip/add operations update database correctly
- Test session persistence
- Test edge cases (no candidates, invalid playlist)
