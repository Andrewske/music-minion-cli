# Rolling Window Shuffle Implementation

## Overview

Transform the Music Minion player from a fixed 50-track queue to a dynamic 100-track rolling window that refills intelligently as tracks finish. This implementation adds:

- **Anti-repetition**: Natural spacing through exclusion windows (~100 tracks between repeats)
- **Smooth shuffle toggle**: Change shuffle mode without interrupting playback
- **Manual table sorting**: Click column headers to sort queue (BPM, title, artist, etc.)
- **Queue persistence**: Survive server restarts with full queue state restoration

### Why This Matters

The current frontend shuffle is simplistic (random selection on each play). The rolling window provides:
1. True anti-repetition (no track repeats within ~100 plays)
2. Infinite playback (queue automatically extends)
3. Server-side shuffle (consistent across devices)
4. Smart playlist support (filters applied to each new track)

## Task Sequence

1. **[01-database-schema.md](./01-database-schema.md)** - Add `player_queue_state` table for persistence
2. **[02-queue-manager-module.md](./02-queue-manager-module.md)** - Create pure functional queue management core
3. **[03-backend-player-integration.md](./03-backend-player-integration.md)** - Update player API endpoints and add shuffle/sort endpoints
4. **[04-frontend-state-management.md](./04-frontend-state-management.md)** - Update Zustand player store with sort state and smooth actions
5. **[05-frontend-ui-updates.md](./05-frontend-ui-updates.md)** - Wire shuffle button to smooth toggle action

## Success Criteria

### End-to-End Verification

After implementing all tasks, verify the complete system:

#### 1. Basic Playback with Rolling Window
```bash
uv run music-minion --web
# Open http://localhost:5173
# Play a large playlist (500+ tracks)
# Verify 100 tracks loaded initially
# Skip through 60+ tracks
# Verify queue grows dynamically (check queue length in player state)
```

#### 2. Shuffle Toggle (Smooth)
```bash
# During playback:
# 1. Click shuffle button
# Expected: Current track continues playing, no position reset
# 2. Verify queue rebuilt (different tracks ahead)
# 3. Toggle shuffle again
# Expected: Smooth transition back to shuffle mode
```

#### 3. Manual Table Sort
```bash
# During playback:
# 1. Click BPM column header in queue table
# Expected: Shuffle automatically disabled
# Expected: Queue sorted by BPM ascending
# 2. Click again
# Expected: Sort direction flips to descending
```

#### 4. Queue Persistence
```bash
# 1. Play several tracks (advance 10+ positions in queue)
# 2. Stop server (Ctrl+C in terminal)
# 3. Restart server
# 4. Check /api/player/state endpoint
# Expected: Queue restored with same tracks and position
# Expected: is_playing = false (manual resume required)
```

#### 5. Anti-Repetition Verification
```bash
# Play through 120+ tracks in shuffle mode
# Check queue history (inspect queue array in player state)
# Expected: No duplicate track IDs in consecutive 100-track window
```

#### 6. Edge Cases
```bash
# Small playlist (<100 tracks):
# - Play 30-track playlist
# - Expected: All 30 tracks loaded, no errors
# - Expected: Queue doesn't grow beyond playlist size

# Large playlist (1000+ tracks):
# - Play massive playlist
# - Expected: No lag when skipping tracks
# - Check logs for SQL query timing (<100ms per track pull)

# Smart playlist:
# - Create smart playlist with filters (e.g., BPM > 120)
# - Play from it
# - Modify filters while playing
# - Expected: New tracks respect updated filters
```

### Log Verification

Check `music-minion-uvicorn.log` for:
```
INFO: Restoring queue state: 143 tracks
INFO: Queue state restored successfully
INFO: Shuffle enabled (smooth toggle)
INFO: Queue sorted by bpm asc
```

### Database Verification

```bash
sqlite3 ~/.local/share/music-minion/library.db

# Check table exists
SELECT sql FROM sqlite_master WHERE name='player_queue_state';

# Check state saved
SELECT
  shuffle_enabled,
  sort_field,
  json_array_length(queue_track_ids) as queue_size,
  queue_index
FROM player_queue_state;

# Expected output example:
# shuffle_enabled | sort_field | queue_size | queue_index
# 1               | NULL       | 143        | 67
```

## Dependencies

### Prerequisites
- SQLite database schema v31 (will upgrade to v32)
- Existing player implementation in `web/backend/routers/player.py`
- Zustand player store in `web/frontend/src/stores/playerStore.ts`
- WebSocket sync infrastructure (`useSyncWebSocket` hook)

### External Libraries (Already Installed)
- FastAPI (backend API framework)
- Zustand (frontend state management)
- TanStack React Table (for sortable queue table)

### No New Dependencies Required
This implementation uses existing libraries and infrastructure.

## Architecture Notes

### Pure Functional Design
The `queue_manager.py` module follows strict functional principles:
- No global state or singletons
- All state passed as function parameters
- Database connections explicitly passed (no imports of global DB)
- Fully testable in isolation
- Compatible with hot-reload (no module-level state to corrupt)

### Rolling Window Mechanics
```
Initial load: [Track 1, Track 2, ..., Track 100]
                     ^current

After 60 tracks: [Track 1, ..., Track 60, Track 61, ..., Track 160]
                                         ^current

Exclusion list: [Track 61, ..., Track 160, Current Track]
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                 101 tracks excluded from random selection
```

### Lookahead Buffer
- Trigger refill when: `len(queue) - queue_index < 50`
- This maintains 50+ tracks of lookahead buffer
- Prevents UI jank when approaching end of queue
- Background refill (1 track at a time, ~10-50ms each)

### Database Singleton Pattern
- Single row in `player_queue_state` table (id=1)
- `INSERT OR REPLACE` for atomic updates
- Stores queue as JSON array of track IDs
- Minimal storage: ~1KB for 100-track queue

## Performance Characteristics

- **Initial queue load**: ~200-300ms (100 tracks with metadata)
- **Single track pull**: ~10-50ms (random SQL + metadata fetch)
- **Shuffle toggle**: ~300-500ms (rebuild 99 tracks)
- **Database write**: ~5-10ms (single row UPSERT)
- **Memory footprint**: ~50KB per 100-track queue (in-memory state)

## Rollback Plan

If issues arise, rollback is straightforward:

1. **Revert backend**: Restore old `resolve_queue()` logic in `player.py`
2. **Revert frontend**: Change shuffle button back to `toggleShuffle()`
3. **Database**: No cleanup needed (table harmless if unused)

The old 50-track behavior is fully compatible with the new schema.
