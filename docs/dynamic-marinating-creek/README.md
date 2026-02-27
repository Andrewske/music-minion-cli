# Playlist Organizer: Queue Filter & Loop Implementation

## Overview
This implementation modifies the playlist organizer to filter the playback queue to ONLY unassigned tracks (tracks not assigned to any bucket), with automatic looping support. Currently, the queue loads all tracks from the playlist regardless of bucket assignments. After this implementation, the queue will dynamically update in real-time as tracks are assigned/unassigned, and will loop continuously through unassigned tracks.

**Key Changes:**
- New "organizer" playback context type that references bucket sessions
- Queue resolution logic that returns only unassigned tracks from sessions
- Real-time queue updates via WebSocket when tracks are assigned/unassigned
- Unassigned tracks instantly reappear at end of queue (no rebuild wait)
- Automatic looping (shuffle or sequential) when queue exhausts
- Session validation to ensure only active sessions can be played
- Auto-resume last organizing session from localStorage (seamless multi-session workflow)
- Bulk "clear bucket" action for quick organizing pivots

## Task Sequence
1. [00-database-migration.md](./00-database-migration.md) - Add context_session_id column to player_queue_state table
2. [01-extend-playcontext-schema.md](./01-extend-playcontext-schema.md) - Add "organizer" type and session_id to PlayContext schema
3. [02-implement-queue-resolution.md](./02-implement-queue-resolution.md) - Implement queue resolution, shuffle, and looping for organizer context
4. [03-real-time-queue-updates.md](./03-real-time-queue-updates.md) - Add WebSocket-based queue updates on assignment changes
5. [04-frontend-integration.md](./04-frontend-integration.md) - Update frontend to use organizer context and remove manual auto-advance
6. [05-session-validation.md](./05-session-validation.md) - Add validation for organizer playback requests
7. [06-write-tests.md](./06-write-tests.md) - Write automated tests for organizer queue functionality

## Success Criteria

### End-to-End Verification

**Manual Testing:**
1. Start organizer with 20 tracks → verify all unassigned
2. Play first track → verify queue contains only unassigned tracks (dev tools)
3. Assign track via drag-and-drop → verify track finishes playing, then automatically skips to next unassigned
4. Assign 5-10 more tracks → verify queue shrinks in real-time
5. Unassign a track → verify it reappears in queue immediately
6. Let queue play through all unassigned → verify it loops back to start
7. Test shuffle mode → verify loop restart reshuffles
8. Assign all tracks → verify playback stops (empty queue)
9. Apply session → verify playback stops (session no longer active)

**Automated Tests:**
- `test_resolve_organizer_context()` - Queue = unassigned_track_ids
- `test_organizer_loop_sequential()` - Deterministic loop restart
- `test_organizer_loop_shuffle()` - Random loop restart
- `test_queue_update_on_assign()` - Real-time queue filtering
- `test_queue_update_on_unassign()` - Track reappears in queue
- `test_invalid_session_validation()` - 404 for missing/inactive session

**Expected Behavior:**
- Queue always contains ONLY unassigned tracks
- Assigning a track removes it from queue (visible in dev tools)
- Unassigning a track adds it back to queue immediately (appended to end)
- Queue loops automatically when exhausted (shuffle or sequential)
- Currently playing track finishes naturally if assigned, then automatically advances to next unassigned track
- Reopening playlist auto-resumes last organizing session (localStorage)

## Dependencies

**External:**
- Python 3.11+ with `uv` package manager
- Node.js 18+ with npm
- SQLite database with existing bucket session tables

**Internal:**
- `web/backend/queries/buckets.py` - `get_session_with_data()` function
- `web/backend/routers/player.py` - `get_playback_state()`, `_broadcast_state()` functions
- `web/frontend/src/stores/playerStore.ts` - Zustand player store

**Key Assumptions:**
- Bucket session system already implemented and functional
- WebSocket broadcast system operational
- Player queue system uses rolling window (100 tracks max)

## Edge Cases Handled

1. **Empty Queue** - All tracks assigned → playback stops naturally
2. **Current Track Assigned** - Track finishes playing naturally, then automatically advances to next unassigned track
3. **Loop Restart** - Queue rebuilds when all tracks excluded, clearing exclusions for fresh loop
4. **Session State Changes** - Validation prevents playback on inactive sessions
5. **Cross-Device Sync** - WebSocket ensures real-time updates across all devices

## Performance Notes

- `get_session_with_data()`: ~5-10ms indexed query
- Queue updates: Once per assignment (user-initiated)
- WebSocket broadcast: ~50ms latency for multi-device sync
- Memory: Constant (100-track window regardless of playlist size)
