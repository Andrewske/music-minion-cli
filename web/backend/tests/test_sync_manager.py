import asyncio
import time

import pytest
from unittest.mock import AsyncMock
from web.backend.sync_manager import SyncManager, remaining_track_seconds
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
async def test_broadcast_drops_slow_connection_without_stalling_others():
    """A hung client is dropped after send_timeout; fast clients still receive."""
    manager = SyncManager()
    manager.send_timeout = 0.01
    ws_fast = AsyncMock()
    ws_slow = AsyncMock()

    async def hang(message):
        await asyncio.sleep(5)

    ws_slow.send_json = hang
    await manager.connect(ws_fast)
    await manager.connect(ws_slow)

    await manager.broadcast("test:event", {})

    ws_fast.send_json.assert_called_once()
    assert ws_fast in manager.connections
    assert ws_slow not in manager.connections


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
        manager.track_end_margin = 0
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


@pytest.mark.anyio
async def test_offline_active_device_keeps_playing_mid_track():
    """A dropped socket mid-track evicts the device but doesn't pause.

    Android Chrome kills a backgrounded tab's WebSocket while its audio keeps
    playing — pausing then would silence the phone on reconnect.
    """
    player_state.reset_state()
    await player_state.update_state(
        {
            "is_playing": True,
            "active_device_id": "phone",
            "current_track": {"id": 1, "duration": 300},
            "position_ms": 0,
            "track_started_at": time.time(),
        },
        broadcast=False,
    )
    try:
        manager = SyncManager()
        manager.grace_period = 0
        ws = AsyncMock()
        await manager.connect(ws)
        await manager.register_device("phone", "Android Chrome", ws)

        manager.disconnect(ws)
        await manager.unregister_device("phone", ws)
        await asyncio.sleep(0.05)  # grace elapses; pause watcher now sleeping

        assert "phone" not in manager.devices
        assert player_state.get_state().is_playing is True
        assert player_state.get_state().active_device_id == "phone"

        # Reconnect cancels the pending pause
        ws2 = AsyncMock()
        await manager.connect(ws2)
        await manager.register_device("phone", "Android Chrome", ws2)
        assert "phone" not in manager.disconnect_timers
        assert player_state.get_state().is_playing is True
    finally:
        player_state.reset_state()


@pytest.mark.anyio
async def test_offline_device_that_advances_is_not_paused():
    """An offline device still calling /next (new track, fresh clock) stays active."""
    player_state.reset_state()
    await player_state.update_state(
        {
            "is_playing": True,
            "active_device_id": "phone",
            "current_track": {"id": 1, "duration": 0.05},
            "position_ms": 0,
            "track_started_at": time.time(),
        },
        broadcast=False,
    )
    try:
        manager = SyncManager()
        manager.grace_period = 0
        manager.track_end_margin = 0
        ws = AsyncMock()
        await manager.connect(ws)
        await manager.register_device("phone", "Android Chrome", ws)
        manager.disconnect(ws)
        await manager.unregister_device("phone", ws)

        # Device advances over HTTP before the first track's end is checked
        await asyncio.sleep(0.01)
        await player_state.update_state(
            {
                "current_track": {"id": 2, "duration": 300},
                "track_started_at": time.time(),
            },
            broadcast=False,
        )
        await asyncio.sleep(0.1)

        assert player_state.get_state().is_playing is True
        manager.disconnect_timers["phone"].cancel()
    finally:
        player_state.reset_state()


def test_remaining_track_seconds():
    now = time.time()
    track = {"duration": 100}
    assert remaining_track_seconds(track, 0, now - 40) == pytest.approx(60, abs=1)
    assert remaining_track_seconds(track, 30_000, now - 40) == pytest.approx(30, abs=1)
    assert remaining_track_seconds(track, 0, now - 500) == 0
    assert remaining_track_seconds({"duration": None}, 0, now) == 0
    assert remaining_track_seconds(None, 0, now) == 0
    assert remaining_track_seconds(track, 0, None) == 0
