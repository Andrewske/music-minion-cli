"""Centralized playback state management with immutability guarantees."""

import time
from asyncio import Lock
from typing import Callable, Optional
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel
from .schemas import PlayContext

_state_lock = Lock()

class PlaybackState(BaseModel):
    """Immutable playback state."""
    model_config = ConfigDict(
        frozen=True,
        alias_generator=to_camel,
        populate_by_name=True
    )

    current_track: Optional[dict] = None
    queue: tuple[dict, ...] = ()  # tuple for true immutability
    queue_index: int = 0
    position_ms: int = 0
    track_started_at: Optional[float] = None
    is_playing: bool = False
    active_device_id: Optional[str] = None
    shuffle_enabled: bool = True
    sort_spec: Optional[dict] = None
    current_context: Optional[PlayContext] = None
    position_in_playlist: int = 0
    server_time: float = 0
    current_history_id: Optional[int] = None
    duration_ms: int = 0

_state = PlaybackState()

def get_state() -> PlaybackState:
    """Get current state (read-only snapshot)."""
    return _state

def get_state_dict() -> dict:
    """Get state as dict with server time for API responses."""
    state = _state.model_dump(by_alias=True)
    state["serverTime"] = time.time()
    return state

async def update_state(
    update: dict | Callable[[PlaybackState], PlaybackState],
    broadcast: bool = True
) -> PlaybackState:
    """Thread-safe state update with optional broadcast.

    Args:
        update: Either a dict of field updates, or a function (state) -> new_state
        broadcast: Whether to broadcast after update (default True)

    Returns:
        The new state
    """
    global _state

    async with _state_lock:
        if callable(update):
            _state = update(_state)
        else:
            # Convert queue list to tuple if present
            if "queue" in update and isinstance(update["queue"], list):
                update = {**update, "queue": tuple(update["queue"])}
            _state = _state.model_copy(update=update)

        if broadcast:
            from .sync_manager import sync_manager
            await sync_manager.broadcast("playback:state", get_state_dict())

        return _state


def reset_state() -> None:
    """Reset state to initial values. For testing only."""
    global _state
    _state = PlaybackState()
