import asyncio
import time
from typing import Any
from fastapi import WebSocket
from loguru import logger


class SyncManager:
    """Manages WebSocket connections and broadcasts state updates.

    Stores current state so reconnecting clients get immediate sync.
    Handles device registry with grace period for disconnects.
    """

    # Seconds a device may stay offline before eviction (overridable in tests)
    grace_period: float = 30
    # Per-connection send timeout during broadcast (overridable in tests)
    send_timeout: float = 2.0

    def __init__(self):
        # Set (not list): cleanup uses discard(), so two overlapping broadcasts
        # can both drop the same dead connection without a ValueError race.
        self.connections: set[WebSocket] = set()
        # Device registry: {device_id: {id, name, connected_at, connections}}
        # `connections` is the set of live websockets for that device — one
        # machine can open several tabs/apps that all share the same persisted
        # device-id, so a device is online while ANY of them is connected.
        self.devices: dict[str, dict[str, Any]] = {}
        # Disconnect grace timers: {device_id: asyncio.Task}
        self.disconnect_timers: dict[str, asyncio.Task] = {}

    async def connect(self, ws: WebSocket) -> None:
        """Accept and store a new WebSocket connection."""
        await ws.accept()
        self.connections.add(ws)

    def disconnect(self, ws: WebSocket) -> None:
        """Remove a WebSocket connection (idempotent)."""
        self.connections.discard(ws)

    async def broadcast_comparison_update(
        self, playlist_id: int, progress: dict
    ) -> None:
        """Broadcast comparison update to all connected devices.

        No caching - just notifies devices that a comparison happened.
        Devices re-query for next pair themselves.
        """
        await self.broadcast(
            "comparison:update",
            {
                "playlist_id": playlist_id,
                "progress": progress,
            },
        )

    async def register_device(
        self, device_id: str, device_name: str, ws: WebSocket
    ) -> None:
        """Register a device or add a connection to an existing one."""
        # Cancel pending disconnect timer if reconnecting
        if device_id in self.disconnect_timers:
            self.disconnect_timers[device_id].cancel()
            del self.disconnect_timers[device_id]

        existing = self.devices.get(device_id)
        connections: set[WebSocket] = existing["connections"] if existing else set()
        connections.add(ws)

        self.devices[device_id] = {
            "id": device_id,
            "name": device_name,
            "connected_at": existing["connected_at"] if existing else time.time(),
            "connections": connections,
        }

        # Broadcast updated device list
        await self.broadcast_device_list()

    async def unregister_device(
        self, device_id: str, ws: WebSocket | None = None
    ) -> None:
        """Drop one connection; start grace period only when none remain.

        A device with another live connection (e.g. a second tab sharing the
        same persisted device-id) stays online — so a closing tab can't evict
        it or pause playback.
        """
        device = self.devices.get(device_id)
        if device is None:
            return

        if ws is not None:
            device["connections"].discard(ws)

        # Still has live connections — device is online, nothing to do.
        if device["connections"]:
            return

        # No connections left: (re)start grace timer before eviction.
        if device_id in self.disconnect_timers:
            self.disconnect_timers[device_id].cancel()

        async def remove_after_grace():
            """Remove device after the grace period if it didn't reconnect."""
            await asyncio.sleep(self.grace_period)
            dev = self.devices.get(device_id)
            if dev is None or dev["connections"]:
                return  # already gone, or reconnected during grace

            del self.devices[device_id]
            await self.broadcast_device_list()

            # Auto-pause if the genuinely-active device went offline
            from .player_state import get_state, update_state

            state = get_state()
            if state.active_device_id == device_id:
                elapsed_ms = 0
                if state.track_started_at:
                    elapsed_ms = int((time.time() - state.track_started_at) * 1000)

                await update_state(
                    {
                        "is_playing": False,
                        "active_device_id": None,
                        "position_ms": state.position_ms + elapsed_ms,
                        "track_started_at": None,
                    }
                )
                # Note: broadcast happens inside update_state()

        # Start grace timer
        self.disconnect_timers[device_id] = asyncio.create_task(remove_after_grace())

    def get_current_state(self) -> dict:
        """Get current application state for new connections."""
        from .player_state import get_state_dict

        return {
            "comparison": None,  # No global comparison state - per-device
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

    async def broadcast_device_list(self) -> None:
        """Broadcast updated device list to all clients."""
        devices = [
            {
                "id": device_id,
                "name": device_info["name"],
                "connected_at": device_info["connected_at"],
            }
            for device_id, device_info in self.devices.items()
        ]
        await self.broadcast("devices:updated", devices)

    async def _send_to(self, conn: WebSocket, message: dict) -> bool:
        """Send to one connection with a timeout. Returns True on success."""
        try:
            await asyncio.wait_for(conn.send_json(message), timeout=self.send_timeout)
            return True
        except Exception:
            return False

    async def broadcast(self, event_type: str, data: dict) -> None:
        """Send a message to all connected clients.

        Sends run concurrently with a per-send timeout so one slow/half-open
        client can't stall the others. Failed or timed-out connections are
        discarded (safe under overlapping broadcasts — connections is a set).
        """
        message = {
            "type": event_type,
            "data": data,
            "ts": time.time(),
        }
        conns = list(self.connections)
        if not conns:
            return

        results = await asyncio.gather(*(self._send_to(c, message) for c in conns))
        for conn, ok in zip(conns, results):
            if not ok:
                logger.warning("Dropping dead/unresponsive WebSocket from broadcast")
                self.connections.discard(conn)


# Singleton instance
sync_manager = SyncManager()
