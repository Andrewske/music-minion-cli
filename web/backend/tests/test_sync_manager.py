import pytest
from unittest.mock import AsyncMock
from web.backend.sync_manager import SyncManager


@pytest.mark.anyio
async def test_connect_accepts_and_stores_websocket():
    manager = SyncManager()
    ws = AsyncMock()
    await manager.connect(ws)
    ws.accept.assert_called_once()
    assert ws in manager.connections


@pytest.mark.anyio
async def test_disconnect_removes_websocket():
    manager = SyncManager()
    ws = AsyncMock()
    await manager.connect(ws)
    manager.disconnect(ws)
    assert ws not in manager.connections


@pytest.mark.anyio
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


@pytest.mark.anyio
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
