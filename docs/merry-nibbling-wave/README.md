# Remove Sessions from Comparison Mode + Consolidate to Playlist-Only

## Overview

Remove session persistence from comparison mode AND consolidate global/playlist ranking into a single unified playlist-based system. The "All" smart playlist becomes the global library ranking, eliminating dual code paths.

**Key Changes:**
1. **Remove sessions**: Drop `playlist_ranking_sessions` table, stateless progress tracking
2. **Migrate global → "All"**: Copy all global rankings/comparisons to "All" playlist with logging
3. **Consolidate tables**: Drop `elo_ratings` and `comparison_history` (use playlist tables only)
4. **Single mode**: Remove global/playlist distinction, everything is playlist-based
5. **Stateless device sync**: No backend caching, all queries fresh (optimized with indexes)
6. **No prefetch**: Fetch pairs on demand only
7. **Performance**: Composite indexes + strategic pairing for <100ms queries at 5000 tracks

## Why This Works

- User has created "All" smart playlist (contains entire library)
- Never uses session-level analytics (only overall progress)
- Needs device sync (desktop playing, phone picking winners)
- ~5000 tracks total, playlists <500 tracks
- Optimized queries fast enough without caching/prefetch

## Behavior Changes

**Global rating propagation removed**: Previously, the first 5 playlist comparisons per track would propagate to global ratings via `should_affect_global_ratings()`. This is removed because:
- The "All" playlist now serves as the global ranking
- Comparing tracks in "All" directly updates what was previously "global"
- Other playlist comparisons are intentionally isolated to that playlist's context

**"All" playlist deletion protected**: The "All" playlist cannot be deleted via UI or CLI. Deleting it would lose all global ranking data. The delete option is hidden/disabled for this playlist.

## Task Sequence

1. [01-database-migration.md](./01-database-migration.md) - Migrate global data to "All" playlist, add indexes, backup old tables
2. [02-config-cache-playlist-id.md](./02-config-cache-playlist-id.md) - Cache "All" playlist ID for performance
3. [03-database-layer-refactor.md](./03-database-layer-refactor.md) - Remove global/session functions, add stateless queries
4. [04-backend-api-refactor.md](./04-backend-api-refactor.md) - Simplify endpoints, remove caching, consolidate schemas
5. [05-frontend-refactor.md](./05-frontend-refactor.md) - Remove session/mode from store, simplify API client, update UI
6. [06-cli-refactor.md](./06-cli-refactor.md) - Remove filters/session from state, update handlers and commands

## Success Criteria

### End-to-End Verification

After completing all tasks, verify the entire implementation:

**1. Database Migration**
```bash
uv run python -c "
from music_minion.core.database import get_db_connection

with get_db_connection() as conn:
    cursor = conn.execute('SELECT id FROM playlists WHERE name = \"All\"')
    all_id = cursor.fetchone()['id']

    cursor = conn.execute('SELECT COUNT(*) FROM playlist_elo_ratings WHERE playlist_id = ?', (all_id,))
    print(f'✅ All playlist has {cursor.fetchone()[0]} rated tracks')

    cursor = conn.execute(\"SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '_backup_%'\")
    assert len(cursor.fetchall()) == 3, 'Old tables not backed up!'
    print('✅ Old tables backed up')
"
```

**2. Stateless Progress (CLI)**
```bash
music-minion --dev
# Do 5 comparisons, quit, restart
# Verify progress picks up where you left off
```

**3. Backend API**
```bash
curl -X POST http://localhost:8642/api/comparisons/start \
  -H "Content-Type: application/json" \
  -d '{"playlist_id": 1}'
# Should return pair + progress, no session_id
```

**4. Frontend (Web)**
```bash
music-minion --web
# Open http://localhost:5173
# Verify: Only playlist selector (no mode toggle)
# Verify: Progress displays correctly
# Verify: Completion message shows when done
```

**5. Performance (5000 Tracks)**
```bash
uv run python -c "
import time
from music_minion.domain.rating.database import get_next_playlist_pair
from music_minion.core.config import get_all_playlist_id

start = time.time()
for i in range(10):
    get_next_playlist_pair(get_all_playlist_id())
elapsed = time.time() - start

print(f'✅ Avg query time: {elapsed/10*1000:.1f}ms')
assert elapsed/10 < 0.1, 'Queries too slow!'
"
```

**6. Device Sync**
```bash
# Terminal 1: music-minion --web
# Browser 1 & 2: Both open http://localhost:5173
# Start comparison on both
# Pick winner on Browser 1
# Verify Browser 2 receives WebSocket update
```

## Dependencies

**Prerequisites:**
- "All" smart playlist must exist (contains entire library, no filters)
- Python 3.11+ with `uv` installed
- Database schema version 32 (will migrate to 33)

**External Dependencies:**
- SQLite 3.35+ (for ON CONFLICT clause)
- FastAPI backend running
- Vite frontend dev server

## Implementation Notes

**Migration Safety:**
- Migration logs counts for verification
- Preserves old data in history tables (session_id column kept)
- Fails gracefully if "All" playlist not found

**Performance Critical:**
- Composite index on `(playlist_id, track_a_id, track_b_id)` is **essential**
- Strategic pairing with randomization keeps queries O(N)
- Single transaction ~30% faster than separate commits

**Key Simplifications:**
1. **No sessions**: Stateless progress, simpler code
2. **No modes**: Playlist-only (All = global)
3. **No caching**: Queries fast enough with indexes
4. **No prefetch**: Fetch on demand only
5. **One table per concept**: 2 tables instead of 4
6. **Single transaction**: Faster + atomic

**Net Result:**
- ~550 lines deleted, ~350 lines added = **200 net line reduction**
- <100ms queries even at 5000 tracks
- Fully stateless, zero backend coordination
- Simpler codebase, easier to maintain
