# Materialize Smart Playlists

## Overview
Convert smart playlists from dynamic computation to materialized storage. Instead of evaluating filter rules on every query, smart playlists will store track IDs in `playlist_tracks` (like manual playlists) and refresh on defined triggers.

**Benefits:**
- Sidebar shows correct track count (currently shows 0)
- No temp tables needed for comparisons
- Unified query path for manual and smart playlists
- Faster reads (no filter evaluation per query)

## Task Sequence
1. [01-create-refresh-function.md](./01-create-refresh-function.md) - Add `refresh_smart_playlist_tracks()` function
2. [02-integrate-refresh-with-filter-crud.md](./02-integrate-refresh-with-filter-crud.md) - Call refresh on filter add/update/remove
3. [02b-integrate-refresh-with-skip.md](./02b-integrate-refresh-with-skip.md) - Hybrid skip/unskip handling (targeted delete + refresh)
4. [03-refresh-on-sync.md](./03-refresh-on-sync.md) - Call refresh after `sync local`
5. [04-simplify-get-playlist-tracks.md](./04-simplify-get-playlist-tracks.md) - Simplify 4 functions: remove type branching, use unified queries
6. [05-simplify-comparisons.md](./05-simplify-comparisons.md) - Remove temp table, use direct JOIN
7. [06-migrate-existing-smart-playlists.md](./06-migrate-existing-smart-playlists.md) - One-time migration for existing playlists

## Success Criteria

### End-to-End Verification
1. **Sidebar track counts:** Smart playlists show correct track count in sidebar
2. **Filter CRUD:** Adding/modifying/removing filters updates track count immediately
3. **Sync integration:** `sync local` with new tracks updates smart playlists
4. **Comparisons work:** Start comparison on large smart playlist (5000+ tracks) without hanging
5. **No regressions:** Manual playlists continue to work normally

### Commands to Test
```bash
# Start web app
uv run music-minion --web

# In browser (localhost:5173):
# - Check sidebar shows track counts for smart playlists
# - Navigate to Comparisons, select "All" smart playlist
# - Verify pairs load without delay
```

## Dependencies
- `playlist_tracks` table must exist (already does)
- `evaluate_filters()` function must work correctly (already does)
