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
