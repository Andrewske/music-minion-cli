import pytest
from unittest.mock import AsyncMock
from web.backend.sync_manager import SyncManager
from web.backend import player_state


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


@pytest.mark.anyio
async def test_device_online_while_another_tab_connected():
    """A closing tab must not evict a device whose other tab is still open.

    Two tabs on one machine share the same persisted device-id. When one
    closes, the device stays online and no grace timer is started.
    """
    manager = SyncManager()
    ws1, ws2 = AsyncMock(), AsyncMock()
    await manager.connect(ws1)
    await manager.connect(ws2)
    await manager.register_device("dev", "Computer", ws1)
    await manager.register_device("dev", "Computer", ws2)

    manager.disconnect(ws1)
    await manager.unregister_device("dev", ws1)

    assert "dev" in manager.devices
    assert "dev" not in manager.disconnect_timers


@pytest.mark.anyio
async def test_active_device_pauses_when_all_connections_gone():
    """When the active device's last connection drops, playback pauses."""
    player_state.reset_state()
    await player_state.update_state(
        {"is_playing": True, "active_device_id": "dev"}, broadcast=False
    )
    try:
        manager = SyncManager()
        manager.grace_period = 0
        ws = AsyncMock()
        await manager.connect(ws)
        await manager.register_device("dev", "Computer", ws)

        manager.disconnect(ws)
        await manager.unregister_device("dev", ws)
        await manager.disconnect_timers["dev"]

        assert "dev" not in manager.devices
        assert player_state.get_state().is_playing is False
        assert player_state.get_state().active_device_id is None
    finally:
        player_state.reset_state()


@pytest.mark.anyio
async def test_reconnect_during_grace_keeps_device():
    """Reconnecting before the grace period elapses cancels eviction."""
    manager = SyncManager()
    manager.grace_period = 0
    ws = AsyncMock()
    await manager.connect(ws)
    await manager.register_device("dev", "Computer", ws)

    manager.disconnect(ws)
    await manager.unregister_device("dev", ws)

    # Reconnect before the scheduled grace task runs — cancels the timer.
    ws2 = AsyncMock()
    await manager.connect(ws2)
    await manager.register_device("dev", "Computer", ws2)

    assert "dev" in manager.devices
    assert "dev" not in manager.disconnect_timers
