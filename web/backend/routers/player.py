"""Player router for global playback control and device management."""

import time
from asyncio import Lock
from typing import Optional, Literal
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel
from loguru import logger

from ..deps import get_db
from ..schemas import PlayContext
from ..queue_manager import (
    initialize_queue,
    get_next_track,
    rebuild_queue,
    save_queue_state,
    load_queue_state,
    _resolve_context_to_track_ids,
)
from ..player_state import get_state, get_state_dict, update_state, PlaybackState

router = APIRouter()


# Pydantic models
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


# Lock for protecting /next endpoint from race conditions
_next_lock = Lock()


def _calculate_final_duration() -> int:
    """Calculate total listening duration in ms (accumulated + current segment)."""
    state = get_state()
    duration = int(state.duration_ms)

    if state.track_started_at:
        elapsed = int((time.time() - state.track_started_at) * 1000)
        duration += elapsed

    return duration


def get_playback_state() -> dict:
    """Get current playback state with server time for clock sync."""
    state_dict = get_state_dict()
    state_dict["sortSpec"] = get_state().sort_spec
    return state_dict


async def update_organizer_queue(session_id: str) -> None:
    """Update playback queue if currently playing from this organizer session.

    Removes assigned tracks from queue, adds unassigned tracks back,
    and broadcasts updated state via WebSocket.

    Called by buckets.py when tracks are assigned/unassigned.
    State mutation stays encapsulated in player.py.
    """
    from ..queries.buckets import get_session_with_data
    from ..queries.tracks import batch_fetch_tracks_with_metadata
    from music_minion.core.database import get_db_connection

    # Check if currently playing from this organizer session
    state = get_state()
    if (
        not state.current_context
        or state.current_context.get("type") != "organizer"
        or state.current_context.get("session_id") != session_id
    ):
        return

    # Fetch updated unassigned tracks
    session = get_session_with_data(session_id)
    if not session or session["status"] != "active":
        return

    new_unassigned_set = set(session["unassigned_track_ids"])

    async with _next_lock:
        state = get_state()
        current_queue = state.queue
        current_track_id = state.current_track.get("id") if state.current_track else None

        # Filter queue to only include unassigned tracks
        updated_queue = [track for track in current_queue if track["id"] in new_unassigned_set]

        # Detect newly unassigned tracks and append them
        current_queue_ids = {t["id"] for t in current_queue}
        newly_unassigned_ids = [tid for tid in new_unassigned_set if tid not in current_queue_ids]

        if newly_unassigned_ids:
            with get_db_connection() as db_conn:
                newly_unassigned_tracks = batch_fetch_tracks_with_metadata(newly_unassigned_ids, db_conn)
                updated_queue.extend(newly_unassigned_tracks)

        # Recalculate queue index
        new_index = state.queue_index
        if current_track_id:
            try:
                new_index = next(i for i, t in enumerate(updated_queue) if t["id"] == current_track_id)
            except StopIteration:
                new_index = 0
                logger.info(f"Current track {current_track_id} assigned - will finish then skip to next unassigned")

        await update_state({
            "queue": tuple(updated_queue),
            "queue_index": new_index
        })

    logger.info(f"Updated organizer queue: {len(updated_queue)} unassigned tracks remaining")


@router.post("/play")
async def play(request: PlayRequest, db=Depends(get_db)):
    """Initialize queue and start playback."""
    from ..sync_manager import sync_manager
    from ..queries.tracks import batch_fetch_tracks_with_metadata

    logger.info(f"Play request: track_id={request.track_id}, context={request.context}")

    # Validate organizer session exists and is active
    if request.context.type == "organizer":
        from ..queries.buckets import get_session_with_data
        session = get_session_with_data(request.context.session_id)
        if not session:
            raise HTTPException(404, f"Organizer session {request.context.session_id} not found")
        if session["status"] != "active":
            raise HTTPException(400, f"Organizer session is {session['status']}, cannot play")

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

    # 4. End previous history entry if exists
    state = get_state()
    if state.current_history_id:
        from music_minion.domain.radio.history import end_play
        final_duration = _calculate_final_duration()
        end_play(state.current_history_id, final_duration, reason="new_play")

    # 5. Start new history entry
    from music_minion.domain.radio.history import start_play
    history_id = start_play(
        track_id=queue_tracks[queue_index]["id"],
        source_type="local"  # TODO: derive from track source when multi-source is implemented
    )

    # 6. Update global state
    now = time.time()
    await update_state({
        "current_track": queue_tracks[queue_index],
        "queue": tuple(queue_tracks),
        "queue_index": queue_index,
        "position_ms": 0,
        "track_started_at": now,
        "is_playing": True,
        "active_device_id": active_device_id,
        "current_context": request.context.model_dump(),
        "shuffle_enabled": request.context.shuffle if hasattr(request.context, 'shuffle') else True,
        "sort_spec": None,
        "position_in_playlist": 0,
        "duration_ms": 0,
        "current_history_id": history_id
    })

    # 7. Persist queue state
    save_queue_state(
        context=request.context,
        queue_ids=queue_ids,
        queue_index=queue_index,
        shuffle=request.context.shuffle if hasattr(request.context, 'shuffle') else True,
        sort_spec=None,
        db_conn=db
    )

    return {
        "queue": queue_tracks,
        "queue_index": queue_index,
        "active_device_id": active_device_id,
    }


@router.post("/pause")
async def pause():
    """Pause playback on active device."""
    state = get_state()

    if not state.is_playing:
        return {"message": "Already paused"}

    # Accumulate listening time and update position
    elapsed_ms = 0
    if state.track_started_at:
        elapsed_ms = int((time.time() - state.track_started_at) * 1000)

    await update_state({
        "duration_ms": state.duration_ms + elapsed_ms,
        "position_ms": state.position_ms + elapsed_ms,
        "is_playing": False,
        "track_started_at": None
    })

    return {"message": "Paused"}


@router.post("/resume")
async def resume():
    """Resume playback on active device."""
    state = get_state()

    if state.is_playing:
        return {"message": "Already playing"}

    if not state.current_track:
        raise HTTPException(400, "No track to resume")

    await update_state({
        "is_playing": True,
        "track_started_at": time.time()
    })

    return {"message": "Resumed"}


@router.post("/next")
async def next_track(reason: str = "skip", db=Depends(get_db)):
    """Skip to next track.

    Args:
        reason: Why playback ended - 'skip' (default) or 'completed'
    """
    async with _next_lock:
        from ..queries.tracks import batch_fetch_tracks_with_metadata

        state = get_state()
        if not state.queue:
            raise HTTPException(400, "No queue")

        # Close current history entry
        if state.current_history_id:
            from music_minion.domain.radio.history import end_play
            final_duration = _calculate_final_duration()
            end_play(state.current_history_id, final_duration, reason=reason)

        # Define queue advancement logic
        def advance_queue(s: PlaybackState) -> PlaybackState:
            new_index = s.queue_index + 1
            if new_index >= len(s.queue):
                # End of queue
                return s.model_copy(update={
                    "is_playing": False,
                    "current_track": None,
                    "current_history_id": None
                })

            # Start new history entry
            from music_minion.domain.radio.history import start_play
            history_id = start_play(
                track_id=s.queue[new_index]["id"],
                source_type="local"
            )

            return s.model_copy(update={
                "queue_index": new_index,
                "current_track": s.queue[new_index],
                "position_ms": 0,
                "track_started_at": time.time(),
                "duration_ms": 0,
                "current_history_id": history_id
            })

        await update_state(advance_queue)

        # Refetch state after advancement
        state = get_state()

        # Check lookahead buffer and refill
        if state.current_track:
            tracks_ahead = len(state.queue) - state.queue_index

            if tracks_ahead < 50:  # Lookahead threshold
                # Build exclusion list: all tracks ahead + current
                exclusion_ids = [t["id"] for t in state.queue[state.queue_index:]]

                # Pull 1 new track
                new_track_id = get_next_track(
                    context=state.current_context,
                    exclusion_ids=exclusion_ids,
                    db_conn=db,
                    shuffle=state.shuffle_enabled,
                    sort_spec=state.sort_spec,
                    position_in_sorted=state.position_in_playlist
                )

                # Handle organizer loop restart
                if new_track_id is None and state.current_context.get("type") == "organizer":
                    # Queue exhausted - rebuild for loop restart
                    logger.info("Organizer queue exhausted, rebuilding for loop restart")

                    new_queue_ids = rebuild_queue(
                        context=state.current_context,
                        current_track_id=state.current_track["id"],
                        queue=[t["id"] for t in state.queue],
                        queue_index=state.queue_index,
                        db_conn=db,
                        shuffle=state.shuffle_enabled,
                        sort_spec=state.sort_spec
                    )

                    if new_queue_ids:
                        # Fetch metadata for new queue
                        new_tracks = batch_fetch_tracks_with_metadata(new_queue_ids, db)

                        # Start history entry for first track of new loop
                        from music_minion.domain.radio.history import start_play
                        history_id = start_play(
                            track_id=new_tracks[0]["id"],
                            source_type="local"
                        )

                        await update_state({
                            "queue": tuple(new_tracks),
                            "queue_index": 0,
                            "current_track": new_tracks[0],
                            "position_ms": 0,
                            "track_started_at": time.time(),
                            "current_history_id": history_id
                        })

                        # Save state
                        save_queue_state(
                            context=state.current_context,
                            queue_ids=new_queue_ids,
                            queue_index=0,
                            shuffle=state.shuffle_enabled,
                            sort_spec=state.sort_spec,
                            db_conn=db
                        )

                elif new_track_id:
                    # Normal case: append new track to queue
                    new_tracks = batch_fetch_tracks_with_metadata([new_track_id], db)
                    if new_tracks:  # Defensive check
                        new_position = state.position_in_playlist

                        # Update position for sorted mode
                        if not state.shuffle_enabled:
                            # Get total playlist size for modulo
                            total_size = len(_resolve_context_to_track_ids(state.current_context, db))
                            new_position = (state.position_in_playlist + 100) % total_size

                        await update_state({
                            "queue": state.queue + tuple(new_tracks),
                            "position_in_playlist": new_position
                        })

                        # Save updated state
                        state = get_state()
                        queue_ids = [t["id"] for t in state.queue]
                        save_queue_state(
                            context=state.current_context,
                            queue_ids=queue_ids,
                            queue_index=state.queue_index,
                            shuffle=state.shuffle_enabled,
                            sort_spec=state.sort_spec,
                            db_conn=db
                        )

        return {"status": "next"}


@router.post("/prev")
async def prev_track():
    """Go to previous track."""
    state = get_state()

    if not state.queue:
        raise HTTPException(400, "No queue")

    # If more than 3 seconds in, restart current track
    if state.position_ms > 3000:
        await update_state({
            "position_ms": 0,
            "track_started_at": time.time() if state.is_playing else None
        })
    else:
        # Go to previous track
        new_index = max(0, state.queue_index - 1)

        # Only update history if actually changing tracks
        if new_index != state.queue_index:
            # Close current history entry
            if state.current_history_id:
                from music_minion.domain.radio.history import end_play
                final_duration = _calculate_final_duration()
                end_play(state.current_history_id, final_duration, reason="prev")

            # Start new history entry
            from music_minion.domain.radio.history import start_play
            history_id = start_play(
                track_id=state.queue[new_index]["id"],
                source_type="local"
            )

            await update_state({
                "queue_index": new_index,
                "current_track": state.queue[new_index],
                "position_ms": 0,
                "track_started_at": time.time() if state.is_playing else None,
                "duration_ms": 0,
                "current_history_id": history_id
            })
        else:
            # At start of queue, just restart current track
            await update_state({
                "position_ms": 0,
                "track_started_at": time.time() if state.is_playing else None
            })

    return {"message": "Previous track"}


@router.post("/seek")
async def seek(request: SeekRequest):
    """Seek to position in current track."""
    state = get_state()

    if not state.current_track:
        raise HTTPException(400, "No track playing")

    # Accumulate listening time before seeking
    elapsed_ms = 0
    if state.track_started_at:
        elapsed_ms = int((time.time() - state.track_started_at) * 1000)

    await update_state({
        "duration_ms": state.duration_ms + elapsed_ms,
        "position_ms": request.position_ms,
        "track_started_at": time.time() if state.is_playing else None
    })

    return {"message": "Seeked"}


@router.post("/toggle-shuffle")
async def toggle_shuffle(db=Depends(get_db)):
    """Toggle shuffle without interrupting playback."""
    from ..queries.tracks import batch_fetch_tracks_with_metadata

    state = get_state()
    if not state.current_track:
        raise HTTPException(400, "No active playback")

    # Toggle shuffle state
    new_shuffle = not state.shuffle_enabled

    # Clear sort spec if enabling shuffle
    sort_spec = None if new_shuffle else state.sort_spec

    # Rebuild queue preserving current track
    queue_ids = [t["id"] for t in state.queue]
    new_queue_ids = rebuild_queue(
        context=state.current_context,
        current_track_id=state.current_track["id"],
        queue=queue_ids,
        queue_index=state.queue_index,
        db_conn=db,
        shuffle=new_shuffle,
        sort_spec=sort_spec
    )

    # Fetch full track metadata
    new_queue = batch_fetch_tracks_with_metadata(new_queue_ids, db, preserve_order=True)

    await update_state({
        "queue": tuple(new_queue),
        "shuffle_enabled": new_shuffle,
        "sort_spec": sort_spec
    })

    # Persist state
    save_queue_state(
        context=state.current_context,
        queue_ids=new_queue_ids,
        queue_index=state.queue_index,
        shuffle=new_shuffle,
        sort_spec=sort_spec,
        db_conn=db
    )

    return {
        "shuffle_enabled": new_shuffle,
        "queue_size": len(new_queue)
    }


@router.post("/set-sort")
async def set_sort(request: SetSortRequest, db=Depends(get_db)):
    """Apply manual table sort (disables shuffle)."""
    from ..queries.tracks import batch_fetch_tracks_with_metadata

    state = get_state()
    if not state.current_track:
        raise HTTPException(400, "No active playback")

    sort_spec = {"field": request.field, "direction": request.direction}

    # Rebuild queue with new sort
    queue_ids = [t["id"] for t in state.queue]
    new_queue_ids = rebuild_queue(
        context=state.current_context,
        current_track_id=state.current_track["id"],
        queue=queue_ids,
        queue_index=state.queue_index,
        db_conn=db,
        shuffle=False,
        sort_spec=sort_spec
    )

    new_queue = batch_fetch_tracks_with_metadata(new_queue_ids, db, preserve_order=True)

    await update_state({
        "shuffle_enabled": False,
        "sort_spec": sort_spec,
        "position_in_playlist": 100,
        "queue": tuple(new_queue)
    })

    # Refetch state for persistence
    state = get_state()

    # Persist state
    save_queue_state(
        context=state.current_context,
        queue_ids=new_queue_ids,
        queue_index=state.queue_index,
        shuffle=False,
        sort_spec=sort_spec,
        position_in_playlist=state.position_in_playlist,
        db_conn=db
    )

    return {
        "queue_size": len(new_queue),
        "sort": sort_spec
    }


@router.get("/state")
async def get_player_state():
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
            "is_active": device_id == get_state().active_device_id,
        }
        for device_id, device_info in sync_manager.devices.items()
    ]

    return devices


async def restore_player_queue_state():
    """Restore queue state from database. Called by main app startup handler."""
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

            # Single atomic update instead of multiple mutations
            current_track = None
            if state["queue_index"] < len(queue_tracks):
                current_track = queue_tracks[state["queue_index"]]

            await update_state({
                "queue": tuple(queue_tracks),
                "queue_index": state["queue_index"],
                "shuffle_enabled": state["shuffle_enabled"],
                "sort_spec": state.get("sort_spec"),
                "position_in_playlist": state.get("position_in_playlist", 0),
                "current_context": state["context"],
                "current_track": current_track,
                "is_playing": False,  # Don't auto-resume
            }, broadcast=False)  # No clients connected at startup

            logger.info("Queue state restored successfully")
    except Exception:
        logger.exception("Failed to restore queue state, starting with clean state")
