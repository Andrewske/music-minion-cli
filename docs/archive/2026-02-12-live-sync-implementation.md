# Live Sync Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable real-time state synchronization between multiple devices viewing music.piserver, with CLI remote control support.

**Architecture:** WebSocket endpoint on FastAPI backend broadcasts state changes to all connected clients. Clients update Zustand stores on message receipt. CLI commands POST to remote server when configured.

**Tech Stack:** FastAPI WebSocket, Zustand, TypeScript, Python

---

## Task 1: Backend SyncManager Core

**Files:**
- Create: `web/backend/sync_manager.py`
- Test: `web/backend/tests/test_sync_manager.py`

**Step 1: Write the failing test**

```python
# web/backend/tests/test_sync_manager.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from ..sync_manager import SyncManager


@pytest.mark.asyncio
async def test_connect_accepts_and_stores_websocket():
    manager = SyncManager()
    ws = AsyncMock()

    await manager.connect(ws)

    ws.accept.assert_called_once()
    assert ws in manager.connections


@pytest.mark.asyncio
async def test_disconnect_removes_websocket():
    manager = SyncManager()
    ws = AsyncMock()
    await manager.connect(ws)

    manager.disconnect(ws)

    assert ws not in manager.connections


@pytest.mark.asyncio
async def test_broadcast_sends_to_all_connections():
    manager = SyncManager()
    ws1 = AsyncMock()
    ws2 = AsyncMock()
    await manager.connect(ws1)
    await manager.connect(ws2)

    await manager.broadcast("test:event", {"key": "value"})

    ws1.send_json.assert_called_once()
    ws2.send_json.assert_called_once()
    call_arg = ws1.send_json.call_args[0][0]
    assert call_arg["type"] == "test:event"
    assert call_arg["data"] == {"key": "value"}
    assert "ts" in call_arg


@pytest.mark.asyncio
async def test_broadcast_removes_dead_connections():
    manager = SyncManager()
    ws_alive = AsyncMock()
    ws_dead = AsyncMock()
    ws_dead.send_json.side_effect = Exception("Connection closed")
    await manager.connect(ws_alive)
    await manager.connect(ws_dead)

    await manager.broadcast("test:event", {})

    assert ws_alive in manager.connections
    assert ws_dead not in manager.connections
```

**Step 2: Run test to verify it fails**

Run: `cd web/backend && uv run pytest tests/test_sync_manager.py -v`
Expected: FAIL with "No module named 'sync_manager'"

**Step 3: Write minimal implementation**

```python
# web/backend/sync_manager.py
import time
from fastapi import WebSocket


class SyncManager:
    """Manages WebSocket connections and broadcasts state updates."""

    def __init__(self):
        self.connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        """Accept and store a new WebSocket connection."""
        await ws.accept()
        self.connections.append(ws)

    def disconnect(self, ws: WebSocket) -> None:
        """Remove a WebSocket connection."""
        if ws in self.connections:
            self.connections.remove(ws)

    async def broadcast(self, event_type: str, data: dict) -> None:
        """Send a message to all connected clients."""
        message = {
            "type": event_type,
            "data": data,
            "ts": time.time(),
        }
        dead_connections: list[WebSocket] = []

        for conn in self.connections:
            try:
                await conn.send_json(message)
            except Exception:
                dead_connections.append(conn)

        for conn in dead_connections:
            self.connections.remove(conn)


# Singleton instance
sync_manager = SyncManager()
```

**Step 4: Run test to verify it passes**

Run: `cd web/backend && uv run pytest tests/test_sync_manager.py -v`
Expected: PASS (4 tests)

**Step 5: Commit**

```bash
git add web/backend/sync_manager.py web/backend/tests/test_sync_manager.py
git commit -m "feat(sync): add SyncManager for WebSocket broadcasting"
```

---

## Task 2: WebSocket Endpoint

**Files:**
- Modify: `web/backend/routers/sync.py`
- Modify: `web/backend/main.py`

**Step 1: Write the failing test**

```python
# Add to web/backend/tests/test_sync_manager.py
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect


def test_websocket_endpoint_accepts_connection():
    from ..main import app
    client = TestClient(app)

    with client.websocket_connect("/ws/sync") as websocket:
        # Should receive sync:full on connect
        data = websocket.receive_json()
        assert data["type"] == "sync:full"
        assert "data" in data
```

**Step 2: Run test to verify it fails**

Run: `cd web/backend && uv run pytest tests/test_sync_manager.py::test_websocket_endpoint_accepts_connection -v`
Expected: FAIL with connection refused or 404

**Step 3: Write minimal implementation**

```python
# web/backend/routers/sync.py - ADD to existing file
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from ..sync_manager import sync_manager

router = APIRouter()


def get_current_sync_state() -> dict:
    """Get current state for new connections."""
    # TODO: Will be populated with actual state in later tasks
    return {
        "comparison": None,
        "radio": None,
    }


@router.websocket("/ws/sync")
async def sync_websocket(websocket: WebSocket):
    """WebSocket endpoint for real-time state synchronization."""
    await sync_manager.connect(websocket)
    try:
        # Send current state on connect
        await websocket.send_json({
            "type": "sync:full",
            "data": get_current_sync_state(),
        })

        # Keep connection alive, listen for client messages
        while True:
            # This blocks until message or disconnect
            await websocket.receive_text()
    except WebSocketDisconnect:
        sync_manager.disconnect(websocket)
```

```python
# web/backend/main.py - ADD import and mount
# After existing router imports, add:
from .routers.sync import router as sync_router

# After existing app.include_router calls, add:
app.include_router(sync_router, tags=["sync"])
```

**Step 4: Run test to verify it passes**

Run: `cd web/backend && uv run pytest tests/test_sync_manager.py -v`
Expected: PASS (5 tests)

**Step 5: Commit**

```bash
git add web/backend/routers/sync.py web/backend/main.py
git commit -m "feat(sync): add WebSocket endpoint /ws/sync"
```

---

## Task 3: Broadcast on Comparison Verdict

**Files:**
- Modify: `web/backend/routers/comparisons.py`

**Step 1: Identify integration point**

Read `web/backend/routers/comparisons.py` to find the verdict endpoint. Look for `record_verdict` or similar.

**Step 2: Write the failing test**

```python
# Add to web/backend/tests/test_sync_manager.py
@pytest.mark.asyncio
async def test_verdict_broadcasts_to_connected_clients():
    from ..main import app
    from ..sync_manager import sync_manager
    from fastapi.testclient import TestClient
    from unittest.mock import AsyncMock, patch

    client = TestClient(app)

    # Mock a connected WebSocket
    mock_ws = AsyncMock()
    sync_manager.connections = [mock_ws]

    # Record a verdict (need to mock database)
    with patch('web.backend.routers.comparisons.record_comparison') as mock_record:
        mock_record.return_value = {"next_pair": {"track_a": {}, "track_b": {}}}

        response = client.post("/api/comparisons/verdict", json={
            "session_id": "test",
            "track_a_id": 1,
            "track_b_id": 2,
            "winner_id": 1,
        })

    # Check broadcast was called
    assert mock_ws.send_json.called
    call_arg = mock_ws.send_json.call_args[0][0]
    assert call_arg["type"] == "comparison:advanced"
```

**Step 3: Add broadcast to verdict endpoint**

```python
# web/backend/routers/comparisons.py - ADD import at top
from ..sync_manager import sync_manager

# In the verdict endpoint, after recording the comparison, add:
    # Broadcast to all connected clients
    await sync_manager.broadcast("comparison:advanced", {
        "pair": next_pair_data,
        "prefetched": prefetched_data,
    })
```

**Step 4: Run test to verify it passes**

Run: `cd web/backend && uv run pytest tests/test_sync_manager.py::test_verdict_broadcasts_to_connected_clients -v`
Expected: PASS

**Step 5: Commit**

```bash
git add web/backend/routers/comparisons.py
git commit -m "feat(sync): broadcast comparison:advanced on verdict"
```

---

## Task 4: Frontend useSyncWebSocket Hook

**Files:**
- Create: `web/frontend/src/hooks/useSyncWebSocket.ts`

**Step 1: Write the hook**

```typescript
// web/frontend/src/hooks/useSyncWebSocket.ts
import { useEffect, useRef, useCallback, useState } from 'react';
import { useComparisonStore } from '../stores/comparisonStore';
import { useRadioStore } from '../stores/radioStore';

const WS_URL = import.meta.env.PROD
  ? `wss://${window.location.host}/ws/sync`
  : 'ws://localhost:8642/ws/sync';

export function useSyncWebSocket() {
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const maxReconnectAttempts = 20;

  const handleMessage = useCallback((event: MessageEvent) => {
    try {
      const { type, data } = JSON.parse(event.data);

      switch (type) {
        case 'sync:full':
          // Full state sync on connect
          if (data.comparison?.pair) {
            useComparisonStore.getState().setCurrentPair(
              data.comparison.pair,
              data.comparison.prefetched
            );
          }
          if (data.radio?.nowPlaying) {
            useRadioStore.getState().setNowPlaying(data.radio.nowPlaying);
          }
          break;

        case 'comparison:advanced':
          // Another device marked a winner
          useComparisonStore.getState().setNextPairForComparison(
            data.pair,
            data.prefetched
          );
          break;

        case 'comparison:track_selected':
          // Another device selected a track
          if (data.track) {
            useComparisonStore.getState().setCurrentTrack(data.track);
          }
          useComparisonStore.getState().setIsPlaying(data.isPlaying);
          break;

        case 'radio:now_playing':
          // Radio track changed
          useRadioStore.getState().setNowPlaying(data);
          break;

        case 'ping':
          // Heartbeat, ignore
          break;

        default:
          console.log('Unknown sync message type:', type);
      }
    } catch (error) {
      console.error('Failed to parse sync WebSocket message:', error);
    }
  }, []);

  const connect = useCallback(() => {
    // Prevent duplicate connections
    if (
      wsRef.current?.readyState === WebSocket.OPEN ||
      wsRef.current?.readyState === WebSocket.CONNECTING
    ) {
      return;
    }

    try {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('Connected to sync WebSocket');
        setIsConnected(true);
        reconnectAttemptsRef.current = 0;
      };

      ws.onmessage = handleMessage;

      ws.onclose = () => {
        setIsConnected(false);
        wsRef.current = null;

        // Reconnect with exponential backoff
        reconnectAttemptsRef.current += 1;

        if (reconnectAttemptsRef.current > maxReconnectAttempts) {
          console.log('Max reconnect attempts reached, giving up');
          return;
        }

        const delay = Math.min(
          1000 * Math.pow(2, reconnectAttemptsRef.current - 1),
          60000
        );
        console.log(`Reconnecting in ${delay}ms...`);

        reconnectTimeoutRef.current = window.setTimeout(() => {
          connect();
        }, delay);
      };

      ws.onerror = () => {
        // Error handling - reconnection happens in onclose
      };
    } catch {
      // Connection failed, will retry via onclose
    }
  }, [handleMessage]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    if (wsRef.current) {
      wsRef.current.onclose = null;
      wsRef.current.close();
      wsRef.current = null;
    }

    setIsConnected(false);
    reconnectAttemptsRef.current = 0;
  }, []);

  useEffect(() => {
    connect();
    return () => disconnect();
  }, [connect, disconnect]);

  return { isConnected };
}
```

**Step 2: Verify TypeScript compiles**

Run: `cd web/frontend && npm run type-check` (or `tsc --noEmit`)
Expected: No errors

**Step 3: Commit**

```bash
git add web/frontend/src/hooks/useSyncWebSocket.ts
git commit -m "feat(sync): add useSyncWebSocket hook for frontend"
```

---

## Task 5: Integrate Hook in Root Layout

**Files:**
- Modify: `web/frontend/src/routes/__root.tsx`

**Step 1: Add hook to root layout**

```typescript
// web/frontend/src/routes/__root.tsx - ADD import
import { useSyncWebSocket } from '../hooks/useSyncWebSocket';

// Inside the RootComponent function, ADD:
const { isConnected: isSyncConnected } = useSyncWebSocket();

// OPTIONAL: Add connection indicator to UI (e.g., in header)
// {isSyncConnected ? '🟢' : '🔴'}
```

**Step 2: Remove or reduce polling frequency**

Find the existing 5-second polling for radio now-playing and either:
- Remove it (if radio:now_playing broadcasts cover it)
- Reduce to 30s fallback (belt-and-suspenders)

**Step 3: Verify app still works**

Run: `cd web/frontend && npm run dev`
Open browser, check console for "Connected to sync WebSocket"

**Step 4: Commit**

```bash
git add web/frontend/src/routes/__root.tsx
git commit -m "feat(sync): integrate useSyncWebSocket in root layout"
```

---

## Task 6: Broadcast Track Selection

**Files:**
- Modify: `web/backend/routers/comparisons.py` or create new endpoint

**Step 1: Add track selection endpoint**

```python
# web/backend/routers/comparisons.py - ADD endpoint
from pydantic import BaseModel

class TrackSelectionRequest(BaseModel):
    track_id: int
    is_playing: bool


@router.post("/comparisons/select-track")
async def select_track(request: TrackSelectionRequest):
    """Broadcast track selection to all clients."""
    await sync_manager.broadcast("comparison:track_selected", {
        "track_id": request.track_id,
        "isPlaying": request.is_playing,
    })
    return {"status": "ok"}
```

**Step 2: Frontend calls this endpoint on track select**

```typescript
// web/frontend/src/api/comparisons.ts - ADD function
export async function selectTrack(trackId: number, isPlaying: boolean): Promise<void> {
  await fetch('/api/comparisons/select-track', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ track_id: trackId, is_playing: isPlaying }),
  });
}
```

**Step 3: Call from comparison UI when selecting tracks**

In the comparison component, after `selectAndPlay(track)`, add:
```typescript
selectTrack(track.id, true);
```

**Step 4: Commit**

```bash
git add web/backend/routers/comparisons.py web/frontend/src/api/comparisons.ts
git commit -m "feat(sync): broadcast track selection between devices"
```

---

## Task 7: CLI Remote Commands

**Files:**
- Modify: `src/music_minion/config.py` or config handling
- Modify: `src/music_minion/cli/` (web command handlers)

**Step 1: Add config option**

```python
# In config loading, support:
# [web]
# remote_server = "https://music.piserver:8443"
```

**Step 2: Modify CLI web commands**

```python
# src/music_minion/cli/web_commands.py (or equivalent)
import requests
from music_minion.config import get_config

def get_remote_server() -> str | None:
    """Get remote server URL from config, if set."""
    config = get_config()
    return config.get("web", {}).get("remote_server")


def web_winner():
    """Mark track A as winner - local IPC or remote."""
    remote = get_remote_server()

    if remote:
        # POST to remote server
        response = requests.post(
            f"{remote}/api/comparisons/verdict",
            json={
                "session_id": "remote",  # Server should handle missing session
                "winner_id": "track_a",  # Special value meaning "current track A"
            },
            timeout=5,
        )
        response.raise_for_status()
        print("Winner recorded on remote server")
    else:
        # Existing local IPC behavior
        send_ipc_command("winner")
```

**Step 3: Add similar for play1, play2, seek**

```python
def web_play1():
    remote = get_remote_server()
    if remote:
        requests.post(f"{remote}/api/comparisons/select-track",
                     json={"track_id": "track_a", "is_playing": True}, timeout=5)
    else:
        send_ipc_command("play1")

def web_play2():
    remote = get_remote_server()
    if remote:
        requests.post(f"{remote}/api/comparisons/select-track",
                     json={"track_id": "track_b", "is_playing": True}, timeout=5)
    else:
        send_ipc_command("play2")
```

**Step 4: Commit**

```bash
git add src/music_minion/cli/ src/music_minion/config.py
git commit -m "feat(sync): add CLI remote command support"
```

---

## Task 8: Radio Now-Playing Broadcast

**Files:**
- Modify: `web/backend/routers/radio.py`

**Step 1: Find track-started endpoint**

The Liquidsoap callback that reports when a track starts playing.

**Step 2: Add broadcast**

```python
# web/backend/routers/radio.py - in track_started endpoint
from ..sync_manager import sync_manager

# After recording the track started:
await sync_manager.broadcast("radio:now_playing", {
    "track": track_data,
    "position_ms": 0,
    "started_at": time.time(),
})
```

**Step 3: Commit**

```bash
git add web/backend/routers/radio.py
git commit -m "feat(sync): broadcast radio:now_playing on track start"
```

---

## Task 9: End-to-End Testing

**Manual verification checklist:**

1. Start backend: `cd web/backend && uv run uvicorn main:app --reload --port 8642`
2. Start frontend: `cd web/frontend && npm run dev`
3. Open http://localhost:5173 in two browser windows
4. Check both consoles show "Connected to sync WebSocket"
5. Start comparison session in window 1
6. Verify window 2 shows same comparison pair
7. Click track B in window 1 → window 2 shows track B selected
8. Mark winner in window 2 → window 1 advances to next pair
9. Close window 1 → window 2 continues working
10. Reopen window 1 → syncs to current state

**Step: Commit any fixes**

```bash
git add -A
git commit -m "fix(sync): end-to-end testing fixes"
```

---

## Task 10: Deploy to Pi

**Step 1: Rebuild and deploy**

```bash
./scripts/deploy-to-pi.sh
```

**Step 2: Test on actual devices**

1. Open music.piserver on laptop
2. Open music.piserver on phone
3. Run through same checklist as Task 9
4. Test CLI: `music-minion web-winner` with `remote_server` configured

**Step 3: Final commit**

```bash
git add -A
git commit -m "feat(sync): complete live sync implementation"
```

---

## Verification Summary

| Test | Expected Result |
|------|-----------------|
| Two browsers, mark winner | Both advance instantly |
| Track selection syncs | <500ms delay |
| CLI remote command | Triggers broadcast to all clients |
| Disconnect/reconnect | State resyncs on reconnect |
| Radio track change | All clients update |
