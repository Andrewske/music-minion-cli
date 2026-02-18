"""Player router for global playback control and device management."""

import time
from typing import Optional, Literal
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel
from loguru import logger

from ..deps import get_db
from ..queue_manager import (
    initialize_queue,
    get_next_track,
    rebuild_queue,
    save_queue_state,
    load_queue_state,
    _resolve_context_to_track_ids,
)

router = APIRouter()


# Pydantic models
class PlayContext(BaseModel):
    """Playback context for queue generation."""
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    type: Literal["playlist", "track", "builder", "search", "comparison"]
    track_ids: Optional[list[int]] = None  # For comparison context
    playlist_id: Optional[int] = None
    builder_id: Optional[int] = None
    query: Optional[str] = None
    start_index: int = 0
    shuffle: bool = True


class PlayRequest(BaseModel):
    """Request to start playback."""
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    track_id: int
    context: PlayContext
    target_device_id: Optional[str] = None


class SeekRequest(BaseModel):
    """Request to seek to a specific position."""
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    position_ms: int


class SetSortRequest(BaseModel):
    """Request to set manual sort order."""
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    field: str  # 'title', 'artist', 'bpm', 'year', 'elo_rating'
    direction: Literal["asc", "desc"]


class DeviceInfo(BaseModel):
    """Device information."""
    id: str
    name: str
    connected_at: float
    is_active: bool


class PlaybackState(BaseModel):
    """Current playback state."""
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    current_track: Optional[dict] = None
    queue: list[dict] = []
    queue_index: int = 0
    position_ms: int = 0
    track_started_at: Optional[float] = None
    is_playing: bool = False
    active_device_id: Optional[str] = None
    shuffle_enabled: bool = True
    sort_spec: Optional[dict] = None  # NEW: dict with 'field' and 'direction'
    current_context: Optional[PlayContext] = None  # NEW: track playback context
    position_in_playlist: int = 0  # NEW: position tracker for sorted mode
    server_time: float = 0  # For client clock sync


# In-memory state (v1 limitation: lost on server restart)
_playback_state = PlaybackState()


def get_playback_state() -> dict:
    """Get current playback state with server time for clock sync."""
    state = _playback_state.model_dump(by_alias=True)
    state["serverTime"] = time.time()
    state["sortSpec"] = _playback_state.sort_spec  # Ensure sort_spec is included
    return state


def resolve_queue(context: PlayContext, db_conn) -> list[dict]:
    """Resolve play context to a list of tracks (max 50)."""
    from random import shuffle as random_shuffle

    track_ids = []

    if context.type == "track":
        # Single track playback
        track_ids = [context.track_ids[0]] if context.track_ids else []

    elif context.type == "playlist":
        if not context.playlist_id:
            raise HTTPException(400, "playlist_id required for playlist context")

        # Check if it's a smart playlist
        from music_minion.domain.playlists import get_playlist_by_id
        from music_minion.domain.playlists.filters import evaluate_filters

        playlist = get_playlist_by_id(context.playlist_id)
        if not playlist:
            raise HTTPException(404, f"Playlist {context.playlist_id} not found")

        if playlist["type"] == "smart":
            # Smart playlist - evaluate filters dynamically
            tracks = evaluate_filters(context.playlist_id)
            track_ids = [t["id"] for t in tracks]
        else:
            # Manual playlist - query from playlist_tracks table
            cursor = db_conn.execute(
                """
                SELECT track_id FROM playlist_tracks
                WHERE playlist_id = ?
                ORDER BY position
                """,
                (context.playlist_id,)
            )
            track_ids = [row["track_id"] for row in cursor.fetchall()]

    elif context.type == "builder":
        if not context.builder_id:
            raise HTTPException(400, "builder_id required for builder context")

        # Builder context is playlist in builder mode
        cursor = db_conn.execute(
            """
            SELECT track_id FROM playlist_tracks
            WHERE playlist_id = ?
            ORDER BY position
            """,
            (context.builder_id,)
        )
        track_ids = [row["track_id"] for row in cursor.fetchall()]

    elif context.type == "comparison":
        if not context.track_ids:
            raise HTTPException(400, "track_ids required for comparison context")
        track_ids = context.track_ids

    elif context.type == "search":
        # TODO: Implement search query execution
        raise HTTPException(501, "Search context not yet implemented")

    # Apply shuffle on backend
    if context.shuffle:
        track_ids_copy = track_ids.copy()
        random_shuffle(track_ids_copy)
        track_ids = track_ids_copy

    # Limit to 50 tracks
    track_ids = track_ids[:50]

    # Fetch tracks with full metadata and emojis
    if not track_ids:
        return []

    from ..queries.tracks import batch_fetch_tracks_with_metadata
    return batch_fetch_tracks_with_metadata(track_ids, db_conn, preserve_order=True)


@router.post("/play")
async def play(request: PlayRequest, db=Depends(get_db)):
    """Initialize queue and start playback."""
    global _playback_state

    from ..sync_manager import sync_manager
    from ..queries.tracks import batch_fetch_tracks_with_metadata

    logger.info(f"Play request: track_id={request.track_id}, context={request.context}")

    # 1. Initialize queue using queue_manager (not resolve_queue)
    queue_ids = initialize_queue(
        context=request.context,
        db_conn=db,
        window_size=100,  # Changed from 50
        shuffle=request.context.shuffle if hasattr(request.context, 'shuffle') else True,
        sort_spec=None
    )

    # 2. Fetch full track metadata
    queue_tracks = batch_fetch_tracks_with_metadata(queue_ids, db, preserve_order=True)

    if not queue_tracks:
        raise HTTPException(400, "No tracks in queue")

    # 3. Find requested track in queue
    queue_index = 0
    for i, track in enumerate(queue_tracks):
        if track["id"] == request.track_id:
            queue_index = i
            break

    # Set active device (default to first connected device if not specified)
    active_device_id = request.target_device_id
    if not active_device_id and sync_manager.devices:
        active_device_id = next(iter(sync_manager.devices.keys()))

    # 4. Update global state
    now = time.time()
    _playback_state.current_track = queue_tracks[queue_index]
    _playback_state.queue = queue_tracks
    _playback_state.queue_index = queue_index
    _playback_state.position_ms = 0
    _playback_state.track_started_at = now
    _playback_state.is_playing = True
    _playback_state.active_device_id = active_device_id
    _playback_state.current_context = request.context
    _playback_state.shuffle_enabled = request.context.shuffle if hasattr(request.context, 'shuffle') else True
    _playback_state.sort_spec = None
    _playback_state.position_in_playlist = 0

    # 5. Persist queue state
    save_queue_state(
        context=request.context,
        queue_ids=queue_ids,
        queue_index=queue_index,
        shuffle=_playback_state.shuffle_enabled,
        sort_spec=None,
        db_conn=db
    )

    # 6. Broadcast to all devices
    await sync_manager.broadcast("playback:state", get_playback_state())

    return {
        "queue": queue_tracks,
        "queue_index": queue_index,
        "active_device_id": active_device_id,
    }


@router.post("/pause")
async def pause():
    """Pause playback on active device."""
    global _playback_state

    from ..sync_manager import sync_manager

    if not _playback_state.is_playing:
        return {"message": "Already paused"}

    # Calculate current position
    if _playback_state.track_started_at:
        elapsed = time.time() - _playback_state.track_started_at
        _playback_state.position_ms += int(elapsed * 1000)

    _playback_state.is_playing = False
    _playback_state.track_started_at = None

    await sync_manager.broadcast("playback:state", get_playback_state())

    return {"message": "Paused"}


@router.post("/resume")
async def resume():
    """Resume playback on active device."""
    global _playback_state

    from ..sync_manager import sync_manager

    if _playback_state.is_playing:
        return {"message": "Already playing"}

    if not _playback_state.current_track:
        raise HTTPException(400, "No track to resume")

    # Resume from current position
    _playback_state.is_playing = True
    _playback_state.track_started_at = time.time()

    await sync_manager.broadcast("playback:state", get_playback_state())

    return {"message": "Resumed"}


@router.post("/next")
async def next_track(db=Depends(get_db)):
    """Skip to next track."""
    global _playback_state

    from ..sync_manager import sync_manager
    from ..queries.tracks import batch_fetch_tracks_with_metadata

    if not _playback_state.queue:
        raise HTTPException(400, "No queue")

    # Advance queue index
    _playback_state.queue_index += 1

    if _playback_state.queue_index >= len(_playback_state.queue):
        # End of queue
        _playback_state.is_playing = False
        _playback_state.current_track = None
    else:
        # Update current track
        _playback_state.current_track = _playback_state.queue[_playback_state.queue_index]
        _playback_state.position_ms = 0
        _playback_state.track_started_at = time.time()

        # NEW: Check lookahead buffer and refill
        tracks_ahead = len(_playback_state.queue) - _playback_state.queue_index

        if tracks_ahead < 50:  # Lookahead threshold
            # Build exclusion list: all tracks ahead + current
            exclusion_ids = [
                t["id"] for t in _playback_state.queue[_playback_state.queue_index:]
            ]

            # Pull 1 new track
            new_track_id = get_next_track(
                context=_playback_state.current_context,
                exclusion_ids=exclusion_ids,
                db_conn=db,
                shuffle=_playback_state.shuffle_enabled,
                sort_spec=_playback_state.sort_spec,
                position_in_sorted=_playback_state.position_in_playlist
            )

            if new_track_id:
                # Fetch full metadata
                new_tracks = batch_fetch_tracks_with_metadata([new_track_id], db)
                if new_tracks:  # Defensive check
                    _playback_state.queue.append(new_tracks[0])

                    # Update position for sorted mode
                    if not _playback_state.shuffle_enabled:
                        # Get total playlist size for modulo
                        total_size = len(_resolve_context_to_track_ids(_playback_state.current_context, db))
                        _playback_state.position_in_playlist = (_playback_state.position_in_playlist + 100) % total_size

                    # Save updated state
                    queue_ids = [t["id"] for t in _playback_state.queue]
                    save_queue_state(
                        context=_playback_state.current_context,
                        queue_ids=queue_ids,
                        queue_index=_playback_state.queue_index,
                        shuffle=_playback_state.shuffle_enabled,
                        sort_spec=_playback_state.sort_spec,
                        db_conn=db
                    )

        # NEW: Queue trimming - prune old metadata to prevent unbounded growth
        if _playback_state.queue_index > 10:
            # Keep last 10 played tracks with full metadata for UI display
            # Trim older tracks to just ID for exclusion tracking
            old_index = _playback_state.queue_index - 10
            if "title" in _playback_state.queue[old_index]:  # Check if not already pruned
                _playback_state.queue[old_index] = {"id": _playback_state.queue[old_index]["id"]}

    # Broadcast updated state
    await sync_manager.broadcast("playback:state", get_playback_state())

    return {"status": "next"}


@router.post("/prev")
async def prev_track():
    """Go to previous track."""
    global _playback_state

    from ..sync_manager import sync_manager

    if not _playback_state.queue:
        raise HTTPException(400, "No queue")

    # If more than 3 seconds in, restart current track
    if _playback_state.position_ms > 3000:
        _playback_state.position_ms = 0
        _playback_state.track_started_at = time.time() if _playback_state.is_playing else None
    else:
        # Go to previous track
        _playback_state.queue_index = max(0, _playback_state.queue_index - 1)
        _playback_state.current_track = _playback_state.queue[_playback_state.queue_index]
        _playback_state.position_ms = 0
        _playback_state.track_started_at = time.time() if _playback_state.is_playing else None

    await sync_manager.broadcast("playback:state", get_playback_state())

    return {"message": "Previous track"}


@router.post("/seek")
async def seek(request: SeekRequest):
    """Seek to position in current track."""
    global _playback_state

    from ..sync_manager import sync_manager

    if not _playback_state.current_track:
        raise HTTPException(400, "No track playing")

    _playback_state.position_ms = request.position_ms
    _playback_state.track_started_at = time.time() if _playback_state.is_playing else None

    await sync_manager.broadcast("playback:state", get_playback_state())

    return {"message": "Seeked"}


@router.post("/toggle-shuffle")
async def toggle_shuffle(db=Depends(get_db)):
    """Toggle shuffle without interrupting playback."""
    global _playback_state

    from ..sync_manager import sync_manager
    from ..queries.tracks import batch_fetch_tracks_with_metadata

    if not _playback_state.current_track:
        raise HTTPException(400, "No active playback")

    # Toggle shuffle state
    new_shuffle = not _playback_state.shuffle_enabled
    _playback_state.shuffle_enabled = new_shuffle

    # Clear sort spec if enabling shuffle
    sort_spec = None if new_shuffle else _playback_state.sort_spec

    # Rebuild queue preserving current track
    queue_ids = [t["id"] for t in _playback_state.queue]
    new_queue_ids = rebuild_queue(
        context=_playback_state.current_context,
        current_track_id=_playback_state.current_track["id"],
        queue=queue_ids,
        queue_index=_playback_state.queue_index,
        db_conn=db,
        shuffle=new_shuffle,
        sort_spec=sort_spec
    )

    # Fetch full track metadata
    new_queue = batch_fetch_tracks_with_metadata(new_queue_ids, db, preserve_order=True)

    _playback_state.queue = new_queue
    _playback_state.sort_spec = sort_spec

    # Persist state
    save_queue_state(
        context=_playback_state.current_context,
        queue_ids=new_queue_ids,
        queue_index=_playback_state.queue_index,
        shuffle=new_shuffle,
        sort_spec=sort_spec,
        db_conn=db
    )

    # Broadcast
    await sync_manager.broadcast("playback:state", get_playback_state())

    return {
        "shuffle_enabled": new_shuffle,
        "queue_size": len(new_queue)
    }


@router.post("/set-sort")
async def set_sort(request: SetSortRequest, db=Depends(get_db)):
    """Apply manual table sort (disables shuffle)."""
    global _playback_state

    from ..sync_manager import sync_manager
    from ..queries.tracks import batch_fetch_tracks_with_metadata

    if not _playback_state.current_track:
        raise HTTPException(400, "No active playback")

    sort_spec = {"field": request.field, "direction": request.direction}

    # Disable shuffle
    _playback_state.shuffle_enabled = False
    _playback_state.sort_spec = sort_spec

    # Initialize position for sorted mode (starts after initial 100-track window)
    _playback_state.position_in_playlist = 100

    # Rebuild queue with new sort
    queue_ids = [t["id"] for t in _playback_state.queue]
    new_queue_ids = rebuild_queue(
        context=_playback_state.current_context,
        current_track_id=_playback_state.current_track["id"],
        queue=queue_ids,
        queue_index=_playback_state.queue_index,
        db_conn=db,
        shuffle=False,
        sort_spec=sort_spec
    )

    new_queue = batch_fetch_tracks_with_metadata(new_queue_ids, db, preserve_order=True)

    _playback_state.queue = new_queue

    # Persist state
    save_queue_state(
        context=_playback_state.current_context,
        queue_ids=new_queue_ids,
        queue_index=_playback_state.queue_index,
        shuffle=False,
        sort_spec=sort_spec,
        position_in_playlist=_playback_state.position_in_playlist,
        db_conn=db
    )

    # Broadcast
    await sync_manager.broadcast("playback:state", get_playback_state())

    return {
        "queue_size": len(new_queue),
        "sort": sort_spec
    }


@router.get("/state")
async def get_state():
    """Get current playback state."""
    return get_playback_state()


@router.get("/devices")
async def get_devices():
    """List connected devices."""
    from ..sync_manager import sync_manager

    devices = [
        {
            "id": device_id,
            "name": device_info["name"],
            "connected_at": device_info["connected_at"],
            "is_active": device_id == _playback_state.active_device_id,
        }
        for device_id, device_info in sync_manager.devices.items()
    ]

    return devices


async def restore_player_queue_state():
    """Restore queue state from database. Called by main app startup handler."""
    global _playback_state

    from music_minion.core.database import get_db_connection
    from ..queries.tracks import batch_fetch_tracks_with_metadata

    try:
        with get_db_connection() as db:
            state = load_queue_state(db)

            if not state:
                logger.info("No saved queue state found")
                return

            # Validate context still exists
            try:
                context = state["context"]
                # Check if playlist/builder still exists
                if context.type == "playlist":
                    cursor = db.execute("SELECT id FROM playlists WHERE id = ?", (context.playlist_id,))
                    if not cursor.fetchone():
                        logger.warning(f"Saved queue referenced deleted playlist {context.playlist_id}, clearing queue")
                        return
                # Add similar checks for other context types
            except Exception as e:
                logger.warning(f"Failed to validate saved context: {e}")
                return

            logger.info(f"Restoring queue state: {len(state['queue_ids'])} tracks")

            # Fetch full track metadata
            queue_tracks = batch_fetch_tracks_with_metadata(
                state["queue_ids"], db, preserve_order=True
            )

            if not queue_tracks:
                logger.warning("No tracks found for saved queue IDs")
                return

            # Restore state
            _playback_state.queue = queue_tracks
            _playback_state.queue_index = state["queue_index"]
            _playback_state.shuffle_enabled = state["shuffle_enabled"]
            _playback_state.sort_spec = state.get("sort_spec")
            _playback_state.position_in_playlist = state.get("position_in_playlist", 0)
            _playback_state.current_context = state["context"]

            if state["queue_index"] < len(queue_tracks):
                _playback_state.current_track = queue_tracks[state["queue_index"]]

            # Don't auto-resume playback (user must manually press play)
            _playback_state.is_playing = False

            logger.info("Queue state restored successfully")
    except Exception as e:
        logger.exception("Failed to restore queue state, starting with clean state")
