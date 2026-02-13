# Live Sync Design

**Date**: 2026-02-12
**Status**: Approved
**Effort**: 2-3 days

## Problem

Multiple devices viewing `music.piserver` don't stay in sync. When marking a comparison winner on phone, the laptop doesn't update. User wants to control playback from phone while audio plays on computer speakers, and have both devices show the same state instantly (<500ms).

## Solution

WebSocket-based state broadcast from FastAPI backend. All connected clients receive state updates when any client takes an action.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Pi Server                                │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                    FastAPI Backend                          ││
│  │                                                             ││
│  │   REST API              WebSocket /ws/sync                  ││
│  │   (mutations)           (state broadcasts)                  ││
│  │        │                       │                            ││
│  │        ▼                       ▼                            ││
│  │   ┌─────────┐          ┌──────────────┐                    ││
│  │   │ Router  │─────────▶│ SyncManager  │                    ││
│  │   │ Handler │          │ connections[]│                    ││
│  │   └─────────┘          │ broadcast()  │                    ││
│  │                        └──────────────┘                    ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
            │                           │
            │ POST (mutations)          │ WebSocket (broadcasts)
            ▼                           ▼
     ┌───────────┐               ┌───────────┐
     │  Phone    │               │  Laptop   │
     └───────────┘               └───────────┘
            ▲
            │ POST (remote commands)
     ┌───────────┐
     │ Desktop   │
     │ CLI       │
     └───────────┘
```

## Components

### Backend: SyncManager

Simple connection list with broadcast function (~50 lines):

```python
class SyncManager:
    def __init__(self):
        self.connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.connections.append(ws)

    def disconnect(self, ws: WebSocket):
        self.connections.remove(ws)

    async def broadcast(self, event_type: str, data: dict):
        message = {"type": event_type, "data": data, "ts": time.time()}
        dead = []
        for conn in self.connections:
            try:
                await conn.send_json(message)
            except:
                dead.append(conn)
        for conn in dead:
            self.connections.remove(conn)
```

### Backend: WebSocket Endpoint

```python
@router.websocket("/ws/sync")
async def sync_websocket(ws: WebSocket):
    await sync_manager.connect(ws)
    try:
        await ws.send_json({"type": "sync:full", "data": get_current_state()})
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        sync_manager.disconnect(ws)
```

### Events to Broadcast

| Event | Trigger | Payload |
|-------|---------|---------|
| `sync:full` | Client connects | Full comparison + radio state |
| `comparison:advanced` | Verdict recorded | New pair + prefetched |
| `comparison:track_selected` | Track A/B clicked | Track ID, isPlaying |
| `radio:now_playing` | Track started | Track info, position |

### Frontend: useSyncWebSocket Hook

Adapts existing `useIPCWebSocket.ts` pattern:

```typescript
export function useSyncWebSocket() {
  const handleMessage = useCallback((event: MessageEvent) => {
    const { type, data } = JSON.parse(event.data);

    switch (type) {
      case 'sync:full':
        useComparisonStore.getState().setCurrentPair(data.pair, data.prefetched);
        break;
      case 'comparison:advanced':
        useComparisonStore.getState().setNextPairForComparison(data.pair, data.prefetched);
        break;
      case 'comparison:track_selected':
        useComparisonStore.getState().setCurrentTrack(data.track);
        useComparisonStore.getState().setIsPlaying(data.isPlaying);
        break;
      case 'radio:now_playing':
        useRadioStore.getState().setNowPlaying(data);
        break;
    }
  }, []);

  // Reconnection with exponential backoff (1s → 2s → 4s → ... → 60s max)
}
```

### CLI: Remote Commands

Config addition:
```toml
[web]
remote_server = "https://music.piserver:8443"
```

CLI commands check config and POST to remote server if set:
- `web-play1` / `web-play2`
- `web-winner`
- `web-seek-pos` / `web-seek-neg`

## Error Handling

- **Reconnection**: Exponential backoff, max 60s
- **No pause on disconnect**: Unlike IPC, sync disconnect doesn't pause playback
- **Dead connection cleanup**: Remove on broadcast failure
- **State resync**: Server sends `sync:full` on every new connection

## Files to Modify

| File | Change |
|------|--------|
| `web/backend/routers/sync.py` | New WebSocket endpoint + SyncManager |
| `web/backend/routers/comparisons.py` | Add broadcast calls after mutations |
| `web/backend/routers/radio.py` | Add broadcast for now_playing |
| `web/frontend/src/hooks/useSyncWebSocket.ts` | New hook |
| `web/frontend/src/routes/__root.tsx` | Use sync hook, remove 5s polling |
| `src/music_minion/cli/web_commands.py` | Add remote server support |
| `config.toml` | Add `remote_server` option |

## Verification

1. Open `music.piserver` on laptop and phone
2. Start comparison session on laptop
3. Verify phone shows same pair
4. Mark winner on phone → laptop shows next pair instantly
5. Select track B on laptop → phone shows track B selected
6. CLI: `music-minion web-winner` → both devices advance
7. Kill laptop browser → phone continues
8. Reconnect laptop → syncs to current state

## Not In Scope

- Room/session isolation (single user, not needed)
- Authentication (behind Tailscale)
- Horizontal scaling (single Pi server)
- Audio device switching (Icecast handles this - just mute/unmute)
