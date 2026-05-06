---
task: 03-update-progress-calculation
status: complete
depends: []
files:
  - path: src/music_minion/domain/rating/database.py
    action: modify
---

# Update Progress Calculation for Global Counting

## Context
Modify `get_playlist_comparison_progress()` to count comparisons where BOTH tracks are in the current playlist, regardless of which playlist context the comparison was made in.

## Files to Modify/Create
- src/music_minion/domain/rating/database.py (modify)

## Implementation Details

### Change the comparison count query
In `get_playlist_comparison_progress()`, modify lines 439-443.

**Current:**
```python
cursor = conn.execute(
    "SELECT COUNT(*) as count FROM playlist_comparison_history WHERE playlist_id = ?",
    (playlist_id,),
)
```

**New:**
```python
cursor = conn.execute(
    """
    SELECT COUNT(*) as count FROM playlist_comparison_history pch
    WHERE EXISTS (
        SELECT 1 FROM playlist_tracks pt1
        WHERE pt1.track_id = pch.track_a_id AND pt1.playlist_id = ?
    )
    AND EXISTS (
        SELECT 1 FROM playlist_tracks pt2
        WHERE pt2.track_id = pch.track_b_id AND pt2.playlist_id = ?
    )
    """,
    (playlist_id, playlist_id),
)
```

This counts all comparisons where both tracks are members of the playlist, regardless of which playlist context the comparison was originally recorded in.

### Update docstring
Update the function docstring to reflect the new behavior:
```python
def get_playlist_comparison_progress(playlist_id: int) -> dict:
    """Calculate playlist ranking progress based on relevant comparisons.

    Counts comparisons where BOTH tracks are members of this playlist,
    regardless of which playlist the comparison was originally made in.
    This reflects the "global comparison graph" model.
    ...
    """
```

## Verification
1. Check current progress for playlist 384: `get_playlist_comparison_progress(384)`
2. Make a comparison in "All" playlist between two tracks that are both in playlist 384
3. Check progress for playlist 384 again - should increase by 1
4. Verify the percentage calculation is correct
