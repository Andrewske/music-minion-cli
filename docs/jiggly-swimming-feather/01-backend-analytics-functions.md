---
task: 01-backend-analytics-functions
status: done
depends: []
files:
  - path: src/music_minion/domain/playlists/analytics.py
    action: modify
---

# Add Daily Pace Analytics Function

## Context
The playlist analytics system needs a function to calculate daily comparison pace. This is a foundational function that the API layer will call.

## Files to Modify/Create
- `src/music_minion/domain/playlists/analytics.py` (modify)

## Implementation Details

### 1. Add `get_comparison_pace()` function

```python
def get_comparison_pace(playlist_id: int, days: int = 7) -> float:
    """Calculate average comparisons per day over last N days.

    Args:
        playlist_id: Playlist to analyze
        days: Number of days to look back (default 7)

    Returns:
        Average comparisons per day (float). Returns 0.0 if no comparisons.
    """
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            SELECT COUNT(*) as total
            FROM playlist_comparison_history
            WHERE playlist_id = ? AND timestamp >= datetime('now', ? || ' days')
            """,
            (playlist_id, f"-{days}"),
        )
        total = cursor.fetchone()["total"]
        return total / days if days > 0 else 0.0
```

### 2. Register in `get_playlist_analytics()` sections

Add `'pace'` to the available sections dict so it can be requested via the analytics API.

## Verification
```bash
uv run python -c "
from music_minion.domain.playlists.analytics import get_comparison_pace
# Test with All playlist (ID 1 or lookup)
pace = get_comparison_pace(1)
print('Pace:', pace, 'comparisons/day')
"
```
