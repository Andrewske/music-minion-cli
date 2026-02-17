---
task: 01-backend-exclusion-filter
status: done
depends: []
files:
  - path: src/music_minion/domain/playlists/filters.py
    action: modify
---

# Backend: Add Exclusion Filter to Smart Playlist Track Query

## Context
Smart playlists currently return all tracks matching filters. We need to exclude tracks that have been manually skipped by the user, using the existing `playlist_builder_skipped` table.

## Files to Modify/Create
- src/music_minion/domain/playlists/filters.py (modify)

## Implementation Details
Modify `evaluate_filters()` in `filters.py` to exclude skipped tracks at the SQL level. This is more efficient than post-filtering in the router.

Add exclusion filter to the WHERE clause in `evaluate_filters()`:
```python
# After building where_clause from filters, append:
WHERE {where_clause} AND t.id NOT IN (
    SELECT track_id FROM playlist_builder_skipped WHERE playlist_id = ?
)
```

Note: The `playlist_id` parameter is already available in `evaluate_filters(playlist_id)` and used for the ELO ratings JOIN.

The existing `playlist_builder_skipped` table schema:
- `playlist_id INTEGER NOT NULL`
- `track_id INTEGER NOT NULL`
- `skipped_at TIMESTAMP`

No schema changes needed - reuse the table that manual playlist builder already uses.

## Verification
1. Create a smart playlist with filters
2. Manually insert a row into `playlist_builder_skipped` for a track that matches the filters
3. Call `GET /playlists/{playlist_id}/tracks` and verify the skipped track is NOT in results
4. Remove the row from `playlist_builder_skipped` and verify the track reappears
