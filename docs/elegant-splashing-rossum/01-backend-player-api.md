---
task: 01-backend-player-api
status: done
depends: []
files:
  - path: web/backend/routers/player.py
    action: create
  - path: web/backend/main.py
    action: modify
  - path: web/backend/sync_manager.py
    action: modify
---

# Backend Player API

## Context
Foundation layer for the global player. Creates the `/api/player/` router with playback control endpoints, device registry via WebSocket, and state broadcast to all connected devices. This must be completed first as all frontend work depends on it.

## Files to Modify/Create
- `web/backend/routers/player.py` (new)
- `web/backend/main.py` (modify - add player router)
- `web/backend/sync_manager.py` (modify - device registry, playback broadcasts)

## Implementation Details

### 1. Create `/api/player/` router with endpoints:
```python
POST /play          # Initialize queue, set active device
                    # Body: {trackId, context: {type, playlistId?}, targetDeviceId?}
                    # Returns: {queue: Track[], queueIndex, activeDeviceId}

POST /pause         # Pause playback on active device
POST /resume        # Resume playback on active device
POST /next          # Skip to next track
POST /prev          # Go to previous track
POST /seek          # Seek to position {position_ms}

GET /state          # Current playback state
                    # Returns: {currentTrack, queue, queueIndex, position_ms,
                    #           isPlaying, activeDeviceId, shuffleEnabled}

GET /devices        # List connected devices
                    # Returns: [{id, name, connected_at, isActive}]

GET /tracks/{id}/stream  # Audio streaming (modify existing endpoint)
```

### 4. Modify existing `/tracks/{id}/stream` for multi-source:
```python
# Add source-aware redirect before local file handling
cursor = db.execute("SELECT source, source_url FROM tracks WHERE id = ?", (track_id,))
row = cursor.fetchone()
if row and row["source"] == "soundcloud" and row["source_url"]:
    return RedirectResponse(row["source_url"])
# ... existing local file logic (YouTube tracks have local_path, so they work as-is)
```

### 2. Add device registry to WebSocket handler:
- Track connected devices with: `{id, name, connected_at, user_agent}`
- On WebSocket connect: register device (client sends `device:register {id, name}`)
- On disconnect: start 30s grace timer, remove device if not reconnected
- On reconnect (same device ID): cancel pending grace timer
- Broadcast device list changes to all clients: `devices:updated [{devices}]`

```python
# Grace period implementation
disconnect_timers: dict[str, asyncio.Task] = {}

async def on_disconnect(device_id: str):
    async def remove_after_grace():
        await asyncio.sleep(30)
        del devices[device_id]
        await broadcast("devices:updated", list(devices.values()))
        # Auto-pause if this was the active device
        if playback_state.active_device_id == device_id:
            playback_state.is_playing = False
            playback_state.active_device_id = None
            await broadcast("playback:state", get_playback_state())

    disconnect_timers[device_id] = asyncio.create_task(remove_after_grace())

async def on_reconnect(device_id: str, device_info: dict):
    if device_id in disconnect_timers:
        disconnect_timers[device_id].cancel()
        del disconnect_timers[device_id]
    devices[device_id] = device_info
```

**Device state transitions:**
- Active device disconnects → 30s grace period → auto-pause, clear active device
- Any device can call `/resume` to become active and resume playback
- If no devices connected, state persists (queue, position) but `is_playing = false`

### 3. Add playback state management:
- In-memory state: `{active_device_id, current_track, queue, queue_index, track_started_at, position_ms, is_playing}`
- **Note**: State is in-memory only (v1 limitation). Server restart clears playback state.
- On any state change (play/pause/next/prev/seek), broadcast to all devices: `playback:state {full_state}`
- **Position interpolation**: No periodic position broadcasts. Store `track_started_at` (timestamp) and `position_ms` (position at that timestamp). Clients compute: `is_playing ? position_ms + (now - track_started_at + clock_offset) : position_ms`
- **Clock sync**: Include `server_time` in every `playback:state` message. Client computes `clock_offset = server_time - Date.now()` and uses it in position interpolation.
- On pause: set `track_started_at = null`, `position_ms = current_position`
- On resume: set `track_started_at = now`, keep `position_ms`
- On seek: set `track_started_at = now`, `position_ms = seek_position`

### Queue Context Types:
```python
class PlayContext(BaseModel):
    type: Literal["playlist", "track", "builder", "search", "comparison"]
    track_ids: Optional[list[int]] = None  # For comparison context
    playlist_id: Optional[int] = None
    builder_id: Optional[int] = None
    query: Optional[str] = None
    start_index: int = 0
    shuffle: bool = True  # Backend handles all shuffle logic
```

When `/play` is called:
- Resolve context to track list (e.g., fetch playlist tracks)
- Apply shuffle on backend if `shuffle: true` in request (client never shuffles)
- Return queue (max 50 tracks)
- Set active device
- Set `track_started_at = now`, `position_ms = 0`
- Broadcast state to all devices

Shuffle toggle: Client calls `/play` again with same context but `shuffle: false` to get sequential order, or `shuffle: true` to reshuffle.

## Verification

1. Start backend: `uv run music-minion --web`
2. Test device registration:
   ```bash
   # Connect via WebSocket, send device:register
   websocat ws://localhost:8642/ws/sync
   {"type": "device:register", "id": "test-123", "name": "Test Device"}
   ```
3. Test play endpoint:
   ```bash
   curl -X POST http://localhost:8642/api/player/play \
     -H "Content-Type: application/json" \
     -d '{"trackId": 1, "context": {"type": "track"}}'
   ```
4. Verify state broadcast received on WebSocket
5. Test device list: `curl http://localhost:8642/api/player/devices`
