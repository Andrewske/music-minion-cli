# Refactor Player State to Immutable FP Pattern

## Overview

The player backend uses a mutable global `_playback_state` with race conditions:
- Only `/next` endpoint uses a lock - other endpoints race
- Broadcast happens outside lock - clients see stale state
- `sync_manager.py` directly imports and mutates state from a background timer
- No encapsulation - 3 modules access the global directly

This refactor introduces a centralized `player_state.py` module with frozen Pydantic model and async-safe `update_state()` function.

## Task Sequence

1. [01-create-player-state-module.md](./01-create-player-state-module.md) - Create new player_state.py with frozen model and accessors
2. [02-migrate-player-router.md](./02-migrate-player-router.md) - Convert ~15 mutation sites in player.py to use update_state()
3. [03-update-sync-manager.md](./03-update-sync-manager.md) - Fix grace timer race condition, use new accessors
4. [04-write-tests.md](./04-write-tests.md) - Unit tests for immutability and concurrent update behavior

## Success Criteria

End-to-end verification:

1. **Concurrent operations test:**
   ```bash
   music-minion --web
   ```
   - Open two browser tabs
   - Rapidly click play/pause/skip on both
   - Verify no stale state (position jumps, wrong track)

2. **Organizer queue test:**
   - Start organizer session
   - Play from unassigned tracks
   - Assign track while playing
   - Verify queue updates correctly

3. **Device disconnect test:**
   - Connect from mobile browser
   - Close mobile browser
   - Wait 30s for grace period
   - Verify playback pauses cleanly

4. **Unit tests pass:**
   ```bash
   uv run pytest web/backend/tests/test_player_state.py -v
   ```

## Dependencies

- Pydantic v2 (already in project)
- asyncio.Lock (stdlib)

## Rollback

If issues arise:
1. Delete player_state.py
2. Restore `_playback_state` global in player.py
3. Restore direct imports in sync_manager.py
