# Backend WebSocket Core

## Files to Modify/Create
- `web/backend/sync_manager.py` (new)
- `web/backend/tests/test_sync_manager.py` (new)
- `web/backend/routers/live.py` (new - WebSocket endpoint for live sync)
- `web/backend/main.py` (modify - add router)

**Note:** We use `live.py` instead of adding to `sync.py` because `sync.py` already handles filesystem synchronization.

## Implementation Details

### Part 1: SyncManager Class

Create the core connection manager (~50 lines):

```python
# web/backend/sync_manager.py
import time
from typing import Any
from fastapi import WebSocket


class SyncManager:
    """Manages WebSocket connections and broadcasts state updates.

    Stores current state so reconnecting clients get immediate sync.
    """

    def __init__(self):
        self.connections: list[WebSocket] = []
        # Stateful: store last-known state for reconnecting clients
        self.current_comparison: dict[str, Any] | None = None
        self.current_radio: dict[str, Any] | None = None

    async def connect(self, ws: WebSocket) -> None:
        """Accept and store a new WebSocket connection."""
        await ws.accept()
        self.connections.append(ws)

    def disconnect(self, ws: WebSocket) -> None:
        """Remove a WebSocket connection."""
        if ws in self.connections:
            self.connections.remove(ws)

    def set_comparison_state(self, pair: dict, prefetched: dict | None = None) -> None:
        """Update stored comparison state (called after verdict)."""
        self.current_comparison = {"pair": pair, "prefetched": prefetched}

    def set_radio_state(self, now_playing: dict) -> None:
        """Update stored radio state (called on track start)."""
        self.current_radio = now_playing

    def get_current_state(self) -> dict:
        """Get current state for new/reconnecting clients."""
        return {
            "comparison": self.current_comparison,
            "radio": self.current_radio,
        }

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

### Part 2: Tests

```python
# web/backend/tests/test_sync_manager.py
import pytest
from unittest.mock import AsyncMock
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

### Part 3: WebSocket Endpoint

```python
# web/backend/routers/live.py (NEW FILE)
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from ..sync_manager import sync_manager

router = APIRouter()


@router.websocket("/ws/sync")
async def sync_websocket(websocket: WebSocket):
    """WebSocket endpoint for real-time state synchronization."""
    await sync_manager.connect(websocket)
    try:
        # Send current state immediately (stateful - includes comparison/radio)
        await websocket.send_json({
            "type": "sync:full",
            "data": sync_manager.get_current_state(),
        })
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        sync_manager.disconnect(websocket)
```

### Part 4: Register Router

```python
# web/backend/main.py - ADD after existing router imports
from .routers.live import router as live_router

# ADD after existing app.include_router calls
app.include_router(live_router, tags=["live"])
```

## Acceptance Criteria

1. Run tests: `cd web/backend && uv run pytest tests/test_sync_manager.py -v`
   - Expected: 4+ tests pass
2. Start backend: `uv run uvicorn main:app --reload --port 8642`
3. Connect via wscat or browser: `wscat -c ws://localhost:8642/ws/sync`
   - Expected: Receive `{"type": "sync:full", ...}` message

## Dependencies

None - this is the foundational task.

## Commits

```bash
git add web/backend/sync_manager.py web/backend/tests/test_sync_manager.py
git commit -m "feat(live): add stateful SyncManager for WebSocket broadcasting"

git add web/backend/routers/live.py web/backend/main.py
git commit -m "feat(live): add WebSocket endpoint /ws/sync"
```
