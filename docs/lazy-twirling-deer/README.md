# Fix: Comparison Winner + First 5 Affect "All" Playlist

## Overview
Fix the comparison winner button which fails with a SQLite column mismatch error, and reintroduce the "first 5 affect All" feature where the first 5 comparisons per track in any playlist also update that track's rating in the "All" playlist (which serves as global ranking).

## Architecture Decision
The "first 5 affect All" logic is **centralized in the database layer** (`record_playlist_comparison()`). This means:
- Both callers (web router + blessed UI) get the feature automatically
- No signature changes - same 9 parameters
- Single source of truth for business logic
- Easier testing

## Task Sequence
1. [01-rating-database-refactor.md](./01-rating-database-refactor.md) - Fix column names, centralize "first 5" logic
2. [02-comparisons-router-update.md](./02-comparisons-router-update.md) - Verification only (no code changes)

## Success Criteria

### End-to-End Verification

1. **Winner button works:**
   ```bash
   music-minion --web
   # Go to comparison page, select playlist, click winner
   # Should advance to next pair without SQLite error
   ```

2. **First 5 comparisons affect All:**
   ```bash
   uv run python -c "
   from music_minion.core.database import get_db_connection
   from music_minion.core.config import get_all_playlist_id

   with get_db_connection() as conn:
       all_id = get_all_playlist_id()
       # Check a track that was just compared
       cursor = conn.execute('''
           SELECT track_id, comparison_count, rating
           FROM playlist_elo_ratings
           WHERE playlist_id = ?
           ORDER BY comparison_count DESC
           LIMIT 5
       ''', (all_id,))
       for row in cursor.fetchall():
           print(f'Track {row[0]}: {row[1]} comparisons, rating {row[2]:.1f}')
   "
   ```

3. **6th+ comparison isolated:**
   - After 5 comparisons for a track in a playlist, subsequent comparisons should NOT update All playlist
   - Check `affects_global` column: should be 0 for comparisons where both tracks have 5+ comparisons

4. **All playlist guard works:**
   - When comparing directly in the "All" playlist, no propagation logic runs
   - `affects_global` should be 0 for all comparisons in "All" playlist

## Dependencies

- "All" smart playlist must exist (no filters, contains entire library)
- Database schema version 33+ (has `affects_global` column in `playlist_comparison_history`)

## Key Fixes Applied (from plan review)

1. **Column name mismatch** - INSERT now uses `track_a_playlist_rating_before` etc.
2. **ELO calculation order** - Fetch BOTH tracks' All ratings upfront before calculations
3. **Always fetch opponent rating** - Needed for ELO calc even if opponent doesn't affect All
4. **All playlist guard** - Skip propagation when `playlist_id == all_playlist_id`
5. **Minimal tests** - Column name verification + basic recording test
