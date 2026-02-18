"""Player router for global playback control and device management."""

import time
from typing import Optional, Literal
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from ..deps import get_db

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
    server_time: float = 0  # For client clock sync


# In-memory state (v1 limitation: lost on server restart)
_playback_state = PlaybackState()


def get_playback_state() -> dict:
    """Get current playback state with server time for clock sync."""
    state = _playback_state.model_dump(by_alias=True)
    state["serverTime"] = time.time()
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

    # Fetch track data
    if not track_ids:
        return []

    placeholders = ",".join("?" * len(track_ids))
    cursor = db_conn.execute(
        f"""
        SELECT id, title, artist, album, genre, year, bpm, key_signature,
               duration, source, source_url, local_path, elo_rating
        FROM tracks
        WHERE id IN ({placeholders})
        """,
        track_ids
    )

    # Preserve order from track_ids
    tracks_by_id = {row["id"]: dict(row) for row in cursor.fetchall()}
    tracks = [tracks_by_id[tid] for tid in track_ids if tid in tracks_by_id]

    # Batch-fetch emojis for all tracks
    from ..queries.emojis import batch_fetch_track_emojis
    emojis_by_track = batch_fetch_track_emojis([t["id"] for t in tracks], db_conn)

    # Add emojis to each track
    for track in tracks:
        track["emojis"] = emojis_by_track.get(track["id"], [])

    return tracks


@router.post("/play")
async def play(request: PlayRequest, db=Depends(get_db)):
    """Initialize queue and start playback."""
    global _playback_state
    import logging
    logger = logging.getLogger(__name__)

    from ..sync_manager import sync_manager

    logger.info(f"Play request: track_id={request.track_id}, context={request.context}")

    # Resolve context to queue
    queue = resolve_queue(request.context, db)
    logger.info(f"Resolved queue with {len(queue)} tracks")

    if not queue:
        raise HTTPException(400, "No tracks in queue")

    # Find requested track in queue
    queue_index = 0
    for i, track in enumerate(queue):
        if track["id"] == request.track_id:
            queue_index = i
            break

    # Set active device (default to first connected device if not specified)
    active_device_id = request.target_device_id
    if not active_device_id and sync_manager.devices:
        active_device_id = next(iter(sync_manager.devices.keys()))

    # Update state
    now = time.time()
    _playback_state.current_track = queue[queue_index]
    _playback_state.queue = queue
    _playback_state.queue_index = queue_index
    _playback_state.position_ms = 0
    _playback_state.track_started_at = now
    _playback_state.is_playing = True
    _playback_state.active_device_id = active_device_id
    _playback_state.shuffle_enabled = request.context.shuffle

    # Broadcast state to all devices
    await sync_manager.broadcast("playback:state", get_playback_state())

    return {
        "queue": queue,
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
async def next_track():
    """Skip to next track."""
    global _playback_state

    from ..sync_manager import sync_manager

    if not _playback_state.queue:
        raise HTTPException(400, "No queue")

    # Move to next track
    _playback_state.queue_index += 1

    if _playback_state.queue_index >= len(_playback_state.queue):
        # End of queue - stop playback
        _playback_state.is_playing = False
        _playback_state.current_track = None
        _playback_state.track_started_at = None
        _playback_state.position_ms = 0
    else:
        # Start next track
        _playback_state.current_track = _playback_state.queue[_playback_state.queue_index]
        _playback_state.position_ms = 0
        _playback_state.track_started_at = time.time() if _playback_state.is_playing else None

    await sync_manager.broadcast("playback:state", get_playback_state())

    return {"message": "Next track"}


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
