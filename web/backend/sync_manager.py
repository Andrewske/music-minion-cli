import asyncio
import time
from typing import Any
from fastapi import WebSocket


class SyncManager:
    """Manages WebSocket connections and broadcasts state updates.

    Stores current state so reconnecting clients get immediate sync.
    Handles device registry with grace period for disconnects.
    """

    def __init__(self):
        self.connections: list[WebSocket] = []
        # Device registry: {device_id: {id, name, connected_at, ws}}
        self.devices: dict[str, dict[str, Any]] = {}
        # Disconnect grace timers: {device_id: asyncio.Task}
        self.disconnect_timers: dict[str, asyncio.Task] = {}

    async def connect(self, ws: WebSocket) -> None:
        """Accept and store a new WebSocket connection."""
        await ws.accept()
        self.connections.append(ws)

    def disconnect(self, ws: WebSocket) -> None:
        """Remove a WebSocket connection."""
        if ws in self.connections:
            self.connections.remove(ws)

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
        """Register a device or reconnect existing device (cancels grace timer)."""
        # Cancel pending disconnect timer if reconnecting
        if device_id in self.disconnect_timers:
            self.disconnect_timers[device_id].cancel()
            del self.disconnect_timers[device_id]

        # Register device
        self.devices[device_id] = {
            "id": device_id,
            "name": device_name,
            "connected_at": time.time(),
            "ws": ws,
        }

        # Broadcast updated device list
        await self.broadcast_device_list()

    async def unregister_device(self, device_id: str) -> None:
        """Start grace period for device disconnect (30s)."""

        async def remove_after_grace():
            """Remove device after 30s grace period."""
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
