---
task: 01-domain-history-functions
status: done
depends: []
files:
  - path: src/music_minion/domain/radio/history.py
    action: modify
---

# Add History Recording Functions

## Context
Foundation for tracking plays. The domain logic needs `start_play()` and `end_play()` functions before the API layer can use them. The existing query functions need station_id filtering removed.

## Files to Modify/Create
- src/music_minion/domain/radio/history.py (modify)

## Implementation Details

### Add new functions:

```python
def start_play(track_id: int, source_type: str = "local") -> int:
    """Insert a new history entry when a track starts playing. Returns history_id."""
    with get_radio_db_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO radio_history (track_id, source_type, started_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            """,
            (track_id, source_type)
        )
        conn.commit()
        return cursor.lastrowid

def end_play(history_id: int, duration_ms: int, reason: str = "skip") -> None:
    """Update history entry with end time, listening duration, and end reason.

    Args:
        history_id: ID of the history entry to close
        duration_ms: Total time spent listening in milliseconds (accounts for seeking)
        reason: Why playback ended - 'skip', 'completed', or 'new_play'
    """
    with get_radio_db_connection() as conn:
        conn.execute(
            """
            UPDATE radio_history
            SET ended_at = CURRENT_TIMESTAMP, position_ms = ?, end_reason = ?
            WHERE id = ?
            """,
            (duration_ms, reason, history_id)
        )
        conn.commit()

# NOTE: position_ms column stores DURATION (actual listening time), not position.
# Name kept for backwards compatibility with existing data.

# NOTE: Requires adding end_reason column to radio_history table:
# ALTER TABLE radio_history ADD COLUMN end_reason TEXT DEFAULT 'skip'
```

### Update `HistoryEntry` dataclass:
```python
@dataclass(frozen=True)
class HistoryEntry:
    id: int
    track: Track
    source_type: str
    started_at: datetime
    ended_at: Optional[datetime]
    duration_ms: int  # Renamed from position_ms for clarity
    end_reason: Optional[str] = None  # 'skip', 'completed', 'new_play'
    # station_id and station_name REMOVED
```

### Create new `Stats` dataclass (replaces StationStats):
```python
@dataclass(frozen=True)
class Stats:
    total_plays: int
    total_minutes: int  # Actual listening time
    unique_tracks: int
    days_queried: int
```

### Modify existing `get_history_entries()`:
- Remove station_id parameter entirely
- Remove station JOIN and station_name from query
- Query all plays regardless of station

### Rename `get_station_stats()` → `get_stats()`:
- Remove station_id parameter
- Aggregate across ALL history entries
- Use actual listening time: `SUM(position_ms) / 60000` for minutes
```python
def get_stats(days: int = 30) -> Stats:
    with get_radio_db_connection() as conn:
        start_date = (datetime.now() - timedelta(days=days)).date()
        cursor = conn.execute(
            """
            SELECT
                COUNT(*) as total_plays,
                COALESCE(SUM(position_ms) / 60000, 0) as total_minutes,
                COUNT(DISTINCT track_id) as unique_tracks
            FROM radio_history
            WHERE DATE(started_at) >= ?
            """,
            (start_date.isoformat(),)
        )
        row = cursor.fetchone()
        return Stats(
            total_plays=row["total_plays"] or 0,
            total_minutes=row["total_minutes"] or 0,
            unique_tracks=row["unique_tracks"] or 0,
            days_queried=days,
        )
```

### Modify `get_most_played_tracks()`:
- Remove station_id parameter
- Aggregate globally
- Use `SUM(position_ms)` for total_duration

## Verification
```python
# In Python REPL:
from music_minion.domain.radio.history import start_play, end_play, get_history_entries

# Test start_play
history_id = start_play(track_id=1, source_type="local")
print(f"Created history entry: {history_id}")

# Test end_play
end_play(history_id, position_ms=30000)

# Verify entry
entries = get_history_entries(limit=1)
print(entries[0])  # Should show the entry with ended_at and position_ms set
```
