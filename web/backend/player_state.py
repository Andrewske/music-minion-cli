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
    # Monotonic version bumped by update_state() whenever queue CONTENT changes
    # (initialize/refill/rebuild/prune/organizer update). Position-only changes
    # (pause/seek/queue_index advance) do NOT bump it. Clients compare it to
    # decide whether to refetch GET /player/queue.
    queue_version: int = 0
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

# Broadcast ordering: every state snapshot gets a monotonic sequence number
# stamped under _state_lock. Before a snapshot is broadcast (outside the lock),
# we check-and-set _last_broadcast_seq with no await in between (atomic on the
# event loop): a stale snapshot is dropped if a newer one already started
# sending, so a later state can never be overtaken by an earlier one.
_snapshot_seq = 0
_last_broadcast_seq = 0

def get_state() -> PlaybackState:
    """Get current state (read-only snapshot)."""
    return _state

def get_state_dict() -> dict:
    """Get FULL state as dict (queue included) with server time.

    Used for GET /player/state and the sync:full message on WS connect —
    places where the client needs the queue immediately without a second
    round trip. Timestamps are converted to milliseconds for JS Date.now()
    compatibility.
    """
    state = _state.model_dump(by_alias=True)
    state["serverTime"] = time.time() * 1000
    if state.get("trackStartedAt") is not None:
        state["trackStartedAt"] = state["trackStartedAt"] * 1000
    state["queueLength"] = len(_state.queue)
    state["stateSeq"] = _snapshot_seq
    return state


def get_slim_state_dict() -> dict:
    """State dict WITHOUT the queue array — the playback:state broadcast payload.

    Clients keep their queue and refetch GET /player/queue only when
    queueVersion moved past what they hold.
    """
    state = get_state_dict()
    del state["queue"]
    return state


def get_queue_page(offset: int = 0, limit: int = 100) -> dict:
    """One page of the live queue (GET /player/queue).

    Reads a single immutable snapshot, so version/total/tracks are always
    mutually consistent even without holding a lock.
    """
    state = _state
    offset = max(0, offset)
    limit = max(1, min(limit, 500))
    return {
        "version": state.queue_version,
        "total": len(state.queue),
        "offset": offset,
        "tracks": list(state.queue[offset : offset + limit]),
    }

async def update_state(
    update: dict | Callable[[PlaybackState], PlaybackState],
    broadcast: bool = True,
    broadcast_extra: Optional[dict] = None,
) -> PlaybackState:
    """Serialized state update; broadcasts OUTSIDE the state lock.

    Mutation + snapshot happen atomically under _state_lock, then the lock is
    released BEFORE any network I/O so a slow/half-open WebSocket client can
    never stall other state mutations (head-of-line blocking).

    Args:
        update: Either a dict of field updates, or a function (state) -> new_state
        broadcast: Whether to broadcast after update (default True)
        broadcast_extra: Extra top-level fields merged into this one broadcast
            payload only (e.g. pruned_track_id); never persisted in state

    Returns:
        The new state
    """
    global _state, _snapshot_seq

    async with _state_lock:
        old_state = _state
        if callable(update):
            _state = update(_state)
        else:
            # Convert queue list to tuple if present
            if "queue" in update and isinstance(update["queue"], list):
                update = {**update, "queue": tuple(update["queue"])}
            _state = _state.model_copy(update=update)

        # Queue CONTENT changed (identity check: model_copy preserves the tuple
        # reference when "queue" isn't in the update, so position-only changes
        # like pause/seek/index-advance never bump the version).
        if _state.queue is not old_state.queue:
            _state = _state.model_copy(
                update={"queue_version": old_state.queue_version + 1}
            )

        new_state = _state
        _snapshot_seq += 1
        seq = _snapshot_seq
        snapshot: Optional[dict] = None
        if broadcast:
            # Slim payload: everything except the queue array. Clients refetch
            # GET /player/queue when queueVersion advances past what they hold.
            snapshot = get_slim_state_dict()
            if broadcast_extra:
                snapshot.update(broadcast_extra)

    if snapshot is not None:
        await _broadcast_snapshot(seq, snapshot)

    return new_state


async def _broadcast_snapshot(seq: int, snapshot: dict) -> None:
    """Broadcast a state snapshot unless a newer one already went out.

    The check-and-set below has no await between the comparison and the
    assignment, so it is atomic on the event loop: once a newer snapshot
    commits, any older pending snapshot drops itself instead of overtaking it.
    """
    global _last_broadcast_seq
    if seq <= _last_broadcast_seq:
        return  # stale snapshot — a newer state already broadcast
    _last_broadcast_seq = seq
    from .sync_manager import sync_manager
    snapshot["devices"] = [
        {
            "id": device_id,
            "name": info["name"],
            "connected_at": info["connected_at"],
        }
        for device_id, info in sync_manager.devices.items()
    ]
    await sync_manager.broadcast("playback:state", snapshot)


def reset_state() -> None:
    """Reset state to initial values. For testing only."""
    global _state, _snapshot_seq, _last_broadcast_seq
    _state = PlaybackState()
    _snapshot_seq = 0
    _last_broadcast_seq = 0
