import asyncio
import time
from typing import Any
from fastapi import WebSocket
from loguru import logger


def remaining_track_seconds(
    track: dict | None, position_ms: int, track_started_at: float | None
) -> float:
    """Seconds left in the current track at the server clock (0 if over).

    Unknown duration counts as already over, so a dead device can't keep
    the server "playing" forever.
    """
    duration_s = (track or {}).get("duration") or 0
    if not track_started_at or duration_s <= 0:
        return 0.0
    played_s = position_ms / 1000 + (time.time() - track_started_at)
    return max(0.0, duration_s - played_s)


class SyncManager:
    """Manages WebSocket connections and broadcasts state updates.

    Stores current state so reconnecting clients get immediate sync.
    Handles device registry with grace period for disconnects.
    """

    # Seconds a device may stay offline before eviction (overridable in tests)
    grace_period: float = 30
    # Slack past a track's expected end before an offline active device is
    # declared dead (covers gapless handoff + /next latency)
    track_end_margin: float = 60
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
            """Evict after the grace period; pause only once it's provably dead.

            A dropped socket doesn't mean audio stopped: Android Chrome kills
            the WebSocket of a backgrounded tab while its <audio> keeps
            playing and keeps advancing via HTTP /next. So the active device
            is dropped from the list after the grace period, but playback is
            only paused once the current track would have ended without the
            device advancing it.
            """
            await asyncio.sleep(self.grace_period)
            dev = self.devices.get(device_id)
            if dev is None or dev["connections"]:
                return  # already gone, or reconnected during grace

            del self.devices[device_id]
            await self.broadcast_device_list()
            await self._pause_when_track_outlived(device_id)

        # Start grace timer
        self.disconnect_timers[device_id] = asyncio.create_task(remove_after_grace())

    async def _pause_when_track_outlived(self, device_id: str) -> None:
        """Pause if the offline active device lets its track run out.

        Re-checks after each track's remaining time: a device that's still
        playing (offline socket, working HTTP) will have moved on via /next,
        restarting the clock. Cancelled by register_device on reconnect.
        """
        from .player_state import get_state, update_state

        waited = False  # always allow one margin for an in-flight /next
        while True:
            state = get_state()
            if state.active_device_id != device_id or not state.is_playing:
                return
            remaining_s = remaining_track_seconds(
                state.current_track, state.position_ms, state.track_started_at
            )
            if remaining_s <= 0 and waited:
                break
            await asyncio.sleep(remaining_s + self.track_end_margin)
            waited = True

        logger.info(f"Offline device {device_id} let its track end; pausing")
        elapsed_ms = 0
        if state.track_started_at:
            elapsed_ms = int((time.time() - state.track_started_at) * 1000)
        # Note: broadcast happens inside update_state()
        await update_state(
            {
                "is_playing": False,
                "active_device_id": None,
                "position_ms": state.position_ms + elapsed_ms,
                "track_started_at": None,
            }
        )

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
