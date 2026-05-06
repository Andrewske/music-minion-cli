---
task: 01-add-contextual-stats-function
status: complete
depends: []
files:
  - path: src/music_minion/domain/rating/database.py
    action: modify
---

# Add Contextual Track Stats Function

## Context
Create a new function that calculates wins/losses for a track based on comparisons where the opponent is also in the current playlist. This is the foundation for the new "global comparison graph with contextual views" model.

## Files to Modify/Create
- src/music_minion/domain/rating/database.py (modify)

## Implementation Details
Add new function `get_contextual_track_stats()`:

```python
def get_contextual_track_stats(track_id: int, playlist_id: int) -> tuple[int, int]:
    """Calculate wins/losses for track against opponents in this playlist.

    Args:
        track_id: Track to get stats for
        playlist_id: Playlist context (only count opponents in this playlist)

    Returns:
        Tuple of (wins, losses)
    """
    with get_db_connection() as conn:
        # Wins: comparisons where this track won AND opponent is in playlist
        cursor = conn.execute("""
            SELECT COUNT(*) as wins FROM playlist_comparison_history pch
            WHERE pch.winner_id = ?
              AND EXISTS (
                  SELECT 1 FROM playlist_tracks pt
                  WHERE pt.playlist_id = ?
                    AND pt.track_id = CASE
                        WHEN pch.track_a_id = ? THEN pch.track_b_id
                        ELSE pch.track_a_id
                    END
              )
        """, (track_id, playlist_id, track_id))
        wins = cursor.fetchone()["wins"]

        # Losses: comparisons where this track lost AND opponent is in playlist
        cursor = conn.execute("""
            SELECT COUNT(*) as losses FROM playlist_comparison_history pch
            WHERE pch.winner_id != ?
              AND (pch.track_a_id = ? OR pch.track_b_id = ?)
              AND EXISTS (
                  SELECT 1 FROM playlist_tracks pt
                  WHERE pt.playlist_id = ?
                    AND pt.track_id = CASE
                        WHEN pch.track_a_id = ? THEN pch.track_b_id
                        ELSE pch.track_a_id
                    END
              )
        """, (track_id, track_id, track_id, playlist_id, track_id))
        losses = cursor.fetchone()["losses"]

        return (wins, losses)
```

**Key Logic:**
- For wins: Count where `winner_id = track_id` AND opponent is in `playlist_tracks`
- For losses: Count where this track participated but didn't win AND opponent is in `playlist_tracks`
- The `CASE` expression extracts the opponent's ID from the comparison

## Verification
1. Run Python REPL to test the function:
```python
from music_minion.domain.rating.database import get_contextual_track_stats
# Test with a track known to have comparisons
wins, losses = get_contextual_track_stats(5496, 384)
print(f"Track 5496 in playlist 384: {wins} wins, {losses} losses")
```
2. Verify results match manual query of `playlist_comparison_history`
