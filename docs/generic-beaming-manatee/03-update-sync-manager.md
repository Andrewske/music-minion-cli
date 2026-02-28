---
task: 03-update-sync-manager
status: done
depends: [01-create-player-state-module]
files:
  - path: web/backend/sync_manager.py
    action: modify
---

# Update Sync Manager to Use New State Module

## Context
The sync_manager.py directly imports `_playback_state` from player.py and mutates it in the grace timer callback. This creates tight coupling and a race condition. Update to use the centralized state accessors.

## Files to Modify/Create
- web/backend/sync_manager.py (modify)

## Implementation Details

### Update `unregister_device()` grace timer (lines 60-92):

**Before:**
```python
async def unregister_device(self, device_id: str) -> None:
    async def remove_after_grace():
        await asyncio.sleep(30)
        if device_id in self.devices:
            del self.devices[device_id]
            await self.broadcast_device_list()

            # Auto-pause if this was the active device
            from .routers.player import _playback_state
            if _playback_state.active_device_id == device_id:
                _playback_state.is_playing = False
                _playback_state.active_device_id = None
                if _playback_state.track_started_at:
                    elapsed = time.time() - _playback_state.track_started_at
                    _playback_state.position_ms += int(elapsed * 1000)
                    _playback_state.track_started_at = None
                await self.broadcast("playback:state", {...})
```

**After:**
```python
async def unregister_device(self, device_id: str) -> None:
    async def remove_after_grace():
        await asyncio.sleep(30)
        if device_id in self.devices:
            del self.devices[device_id]
            await self.broadcast_device_list()

            # Auto-pause if this was the active device
            from .player_state import get_state, update_state

            state = get_state()
            if state.active_device_id == device_id:
                elapsed_ms = 0
                if state.track_started_at:
                    elapsed_ms = int((time.time() - state.track_started_at) * 1000)

                await update_state({
                    "is_playing": False,
                    "active_device_id": None,
                    "position_ms": state.position_ms + elapsed_ms,
                    "track_started_at": None
                })
                # Note: broadcast happens inside update_state()

    self.disconnect_timers[device_id] = asyncio.create_task(remove_after_grace())
```

### Update `get_current_state()` (lines 94-119):

**Before:**
```python
def get_current_state(self) -> dict:
    from .routers.player import _playback_state

    return {
        "comparison": None,
        "playback": {
            "current_track": _playback_state.current_track,
            "queue": _playback_state.queue,
            # ... manual field access ...
        },
        "devices": [...],
    }
```

**After:**
```python
def get_current_state(self) -> dict:
    from .player_state import get_state_dict

    return {
        "comparison": None,
        "playback": get_state_dict(),
        "devices": [
            {
                "id": device_id,
                "name": device_info["name"],
                "connected_at": device_info["connected_at"],
            }
            for device_id, device_info in self.devices.items()
        ],
    }
```

## Verification

```bash
# Test device disconnect flow
music-minion --web
# Connect from mobile browser
# Close mobile browser
# Wait 30s
# Verify playback pauses (check desktop shows paused state)
```
