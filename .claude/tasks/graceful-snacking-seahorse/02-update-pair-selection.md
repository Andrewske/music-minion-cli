---
task: 02-update-pair-selection
status: complete
depends: [01-add-contextual-stats-function]
files:
  - path: src/music_minion/domain/rating/database.py
    action: modify
---

# Update Pair Selection for Global Skipping + Dynamic Stats

## Context
Modify `get_next_playlist_pair()` to:
1. Skip pairs that have been compared in ANY playlist (not just current)
2. Use dynamic wins calculation instead of stored `playlist_elo_ratings.wins`

## Files to Modify/Create
- src/music_minion/domain/rating/database.py (modify)

## Implementation Details

### Change 1: Global Pair Skipping
In `get_next_playlist_pair()`, modify the NOT IN clause to remove playlist_id filter.

**Current (lines 378-384):**
```sql
AND t.id NOT IN (
    SELECT track_b_id FROM playlist_comparison_history
    WHERE playlist_id = ? AND track_a_id = ?
    UNION
    SELECT track_a_id FROM playlist_comparison_history
    WHERE playlist_id = ? AND track_b_id = ?
)
```

**New:**
```sql
AND t.id NOT IN (
    SELECT track_b_id FROM playlist_comparison_history WHERE track_a_id = ?
    UNION
    SELECT track_a_id FROM playlist_comparison_history WHERE track_b_id = ?
)
```

This removes the `playlist_id = ?` filter, making pair skipping global.

### Change 2: Dynamic Wins in Track Data
After fetching track_a and track_b rows, call `get_contextual_track_stats()` to get dynamic wins/losses and inject into the returned dicts.

**Add after line 410 (before return):**
```python
# Calculate contextual stats
track_a_wins, track_a_losses = get_contextual_track_stats(track_a_id, playlist_id)
track_b_wins, track_b_losses = get_contextual_track_stats(track_b_row["id"], playlist_id)

track_a = dict(track_a_row)
track_b = dict(track_b_row)

# Override stored wins with dynamic calculation
track_a["wins"] = track_a_wins
track_a["comparison_count"] = track_a_wins + track_a_losses
track_b["wins"] = track_b_wins
track_b["comparison_count"] = track_b_wins + track_b_losses

return (track_a, track_b)
```

### Parameter Count Update
The SQL query parameter count will change. Update the parameter tuple accordingly:
- Remove 4 playlist_id parameters from the NOT IN clause
- Keep track_a_id parameters

## Verification
1. Start comparison mode for playlist 384
2. Verify tracks show correct wins/losses (not 0/0)
3. Make a comparison in "All" playlist between two tracks
4. Start comparison mode for a sub-playlist containing both tracks
5. Verify that pair is NOT offered (globally skipped)
