---
task: 02-comparisons-router-update
status: done
depends: [01-rating-database-refactor]
files: []
---

# Verify Router Works (No Changes Needed)

## Context
Since the "first 5 affect All" logic is now centralized in `record_playlist_comparison()`, the router and blessed UI callers require NO changes. The function signature remains the same.

This task is verification-only.

## Files to Modify/Create
None - just verification.

## Implementation Details

### No Code Changes Required

The router at `web/backend/routers/comparisons.py` already calls `record_playlist_comparison()` correctly:

```python
record_playlist_comparison(
    playlist_id=request.playlist_id,
    track_a_id=str(request.track_a_id),
    track_b_id=str(request.track_b_id),
    winner_id=str(request.winner_id),
    track_a_rating_before=track_a_rating,
    track_b_rating_before=track_b_rating,
    track_a_rating_after=track_a_new,
    track_b_rating_after=track_b_new,
    session_id="",
)
```

The blessed UI at `src/music_minion/ui/blessed/events/keys/comparison.py` also calls correctly.

Both callers automatically get the "first 5 affect All" feature since it's handled internally by `record_playlist_comparison()`.

## Verification

```bash
# Start web mode
music-minion --web

# In browser:
# 1. Go to comparison page
# 2. Select a playlist (not "All")
# 3. Click winner button
# 4. Should advance without error

# Check logs for success
tail -20 music-minion-uvicorn.log | grep -E "(POST.*comparisons|ERROR)"

# Verify affects_global column in database
uv run python -c "
from music_minion.core.database import get_db_connection
with get_db_connection() as conn:
    cursor = conn.execute('''
        SELECT affects_global, COUNT(*)
        FROM playlist_comparison_history
        GROUP BY affects_global
    ''')
    for row in cursor.fetchall():
        print(f'affects_global={row[0]}: {row[1]} records')
"

# Verify All playlist ratings updated for first 5 comparisons
uv run python -c "
from music_minion.core.database import get_db_connection
from music_minion.core.config import get_all_playlist_id

with get_db_connection() as conn:
    all_id = get_all_playlist_id()
    cursor = conn.execute('''
        SELECT track_id, comparison_count, rating
        FROM playlist_elo_ratings
        WHERE playlist_id = ?
        ORDER BY comparison_count DESC
        LIMIT 10
    ''', (all_id,))
    print('Top 10 tracks by comparison count in All playlist:')
    for row in cursor.fetchall():
        print(f'  Track {row[0]}: {row[1]} comparisons, rating {row[2]:.1f}')
"
```
