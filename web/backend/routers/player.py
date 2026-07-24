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
    WINDOW_SIZE,
    REFILL_THRESHOLD,
    initialize_queue,
    get_next_tracks,
    rebuild_queue,
    save_queue_state,
    update_queue_position,
    load_queue_state,
    get_unavailable_ids,
    invalidate_context_cache,
)
from ..player_state import (
    get_state,
    get_state_dict,
    get_queue_page,
    update_state,
    PlaybackState,
)

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


# Serializes ALL player mutations (play/pause/resume/next/prev/seek/
# toggle-shuffle/set-sort/transfer, organizer queue updates, dead-track prune).
# Every mutating endpoint does an unlocked-unsafe read-compute-write on
# player_state; this lock makes those sequences atomic w.r.t. each other.
#
# Lock ordering / deadlock avoidance: _player_lock is always acquired BEFORE
# player_state._state_lock (via update_state), never the other way around, and
# asyncio.Lock is NOT reentrant — nothing that holds _player_lock may call
# another helper that acquires it (update_organizer_queue,
# prune_track_from_live_queue, and the endpoints below all acquire it at their
# top level only; _restart_organizer_loop and _calculate_final_duration are
# called while it is held and must not lock).
_player_lock = Lock()


def _calculate_final_duration() -> int:
    """Calculate total listening duration in ms (accumulated + current segment).

    Reads player state — call while holding _player_lock.
    """
    state = get_state()
    duration = int(state.duration_ms)

    if state.track_started_at:
        elapsed = int((time.time() - state.track_started_at) * 1000)
        duration += elapsed

    return duration


def advance_queue(s: PlaybackState, conn=None) -> PlaybackState:
    """Advance to next track in queue.

    If current_track was displaced from queue (e.g., assigned to a bucket),
    queue_index already points at the next track to play — don't +1.

    Args:
        s: Current playback state
        conn: Main-DB connection to reuse for the dead-track check (e.g. the
            request-scoped FastAPI dependency). Opens its own if None.
    """
    current_in_queue = (
        s.queue_index < len(s.queue)
        and s.current_track is not None
        and s.queue[s.queue_index]["id"] == s.current_track["id"]
    )
    new_index = s.queue_index + 1 if current_in_queue else s.queue_index

    # Skip over dead upstream tracks already sitting in the live queue (built before
    # they were marked unavailable). Prevents a dead track being served as "next".
    if conn is not None:
        dead = get_unavailable_ids([t["id"] for t in s.queue], conn)
    else:
        from music_minion.core.database import get_db_connection

        with get_db_connection() as own_conn:
            dead = get_unavailable_ids([t["id"] for t in s.queue], own_conn)
    while new_index < len(s.queue) and s.queue[new_index]["id"] in dead:
        new_index += 1

    if new_index >= len(s.queue):
        # End of queue
        return s.model_copy(
            update={
                "is_playing": False,
                "current_track": None,
                "current_history_id": None,
            }
        )

    from music_minion.domain.radio.history import start_play

    history_id = start_play(
        track_id=s.queue[new_index]["id"],
        source_type=s.queue[new_index].get("source", "local"),
    )

    return s.model_copy(
        update={
            "queue_index": new_index,
            "current_track": s.queue[new_index],
            "position_ms": 0,
            "track_started_at": time.time(),
            "duration_ms": 0,
            "current_history_id": history_id,
        }
    )


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
        or state.current_context.type != "organizer"
        or state.current_context.session_id != session_id
    ):
        return

    # Fetch updated unassigned tracks
    session = get_session_with_data(session_id)
    if not session or session["status"] != "active":
        return

    new_unassigned_set = set(session["unassigned_track_ids"])

    # Organizer pool changed — cached resolved context ids are stale.
    invalidate_context_cache()

    async with _player_lock:
        state = get_state()
        current_queue = state.queue
        current_track_id = (
            state.current_track.get("id") if state.current_track else None
        )

        # Drop dead upstream tracks so they never resurface as the "next" track
        with get_db_connection() as db_conn:
            dead_ids = get_unavailable_ids(
                [t["id"] for t in current_queue] + list(new_unassigned_set), db_conn
            )

        # Filter queue to only include unassigned, still-available tracks
        updated_queue = [
            track
            for track in current_queue
            if track["id"] in new_unassigned_set and track["id"] not in dead_ids
        ]

        # Detect newly unassigned tracks and append them
        current_queue_ids = {t["id"] for t in current_queue}
        newly_unassigned_ids = [
            tid
            for tid in new_unassigned_set
            if tid not in current_queue_ids and tid not in dead_ids
        ]

        if newly_unassigned_ids:
            with get_db_connection() as db_conn:
                newly_unassigned_tracks = batch_fetch_tracks_with_metadata(
                    newly_unassigned_ids, db_conn
                )
                updated_queue.extend(newly_unassigned_tracks)

        # Recalculate queue index
        new_index = state.queue_index
        if current_track_id:
            try:
                new_index = next(
                    i
                    for i, t in enumerate(updated_queue)
                    if t["id"] == current_track_id
                )
            except StopIteration:
                # Current track filtered out (just assigned). Find first forward survivor
                # so the next skip lands on the natural successor instead of jumping to start.
                updated_ids = {t["id"] for t in updated_queue}
                forward_ids = [t["id"] for t in current_queue[state.queue_index + 1 :]]
                target_id = next(
                    (tid for tid in forward_ids if tid in updated_ids), None
                )
                if target_id is not None:
                    new_index = next(
                        i for i, t in enumerate(updated_queue) if t["id"] == target_id
                    )
                else:
                    new_index = len(updated_queue)
                logger.info(
                    f"Current track {current_track_id} assigned; "
                    f"new queue_index={new_index} (target forward={target_id})"
                )

        await update_state({"queue": tuple(updated_queue), "queue_index": new_index})

    logger.info(
        f"Updated organizer queue: {len(updated_queue)} unassigned tracks remaining"
    )


async def prune_track_from_live_queue(track_id: int) -> None:
    """Remove a now-dead track from the live playback queue and broadcast.

    Called when a track is marked unavailable mid-session (e.g. stream returns 410) so
    it stops resurfacing as the "next" track. If it's still the current track, advance
    past it first (advance_queue skips further dead ids); if the client already advanced
    off it, just drop it from the queue WITHOUT advancing again (idempotent — prevents
    the server+client double-advance skipping a good track). A second call for the same
    track is a no-op (track no longer in queue).

    The single broadcast for this mutation carries a top-level `pruned_track_id` hint
    so clients that also auto-advance on stream errors can suppress their own skip
    (additive field — clients ignore unknown keys).
    """
    from music_minion.core.database import get_db_connection

    # Track went dead — cached resolved context ids may still contain it.
    invalidate_context_cache()

    async with _player_lock:
        state = get_state()
        if not state.queue or not any(t["id"] == track_id for t in state.queue):
            return

        def _prune(s: PlaybackState, conn) -> PlaybackState:
            is_current = (
                s.current_track is not None and s.current_track["id"] == track_id
            )
            # Only advance if the dead track is STILL current; otherwise the
            # client (or a racing /next) already moved on — just drop it.
            ns = advance_queue(s, conn) if is_current else s

            new_queue = tuple(t for t in ns.queue if t["id"] != track_id)
            current_id = ns.current_track["id"] if ns.current_track else None
            new_index = min(ns.queue_index, len(new_queue))
            if current_id is not None:
                try:
                    new_index = next(
                        i for i, t in enumerate(new_queue) if t["id"] == current_id
                    )
                except StopIteration:
                    pass

            return ns.model_copy(
                update={"queue": new_queue, "queue_index": new_index}
            )

        with get_db_connection() as conn:
            await update_state(
                lambda s: _prune(s, conn),
                broadcast_extra={"pruned_track_id": track_id},
            )

    logger.info(f"Pruned unavailable track {track_id} from live queue")


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
            raise HTTPException(
                404, f"Organizer session {request.context.session_id} not found"
            )
        if session["status"] != "active":
            raise HTTPException(
                400, f"Organizer session is {session['status']}, cannot play"
            )

    shuffle = request.context.shuffle

    # 1. Initialize queue using queue_manager (not resolve_queue)
    queue_ids = initialize_queue(
        context=request.context,
        db_conn=db,
        window_size=WINDOW_SIZE,
        shuffle=shuffle,
        sort_spec=None,
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

    # Set active device (default to first connected device if not specified).
    # A stale target (device no longer connected) must not win — otherwise
    # playback routes to a ghost and no device ever produces audio.
    active_device_id = request.target_device_id
    if active_device_id and active_device_id not in sync_manager.devices:
        active_device_id = None
    if not active_device_id and sync_manager.devices:
        active_device_id = next(iter(sync_manager.devices.keys()))

    async with _player_lock:
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
            source_type=queue_tracks[queue_index].get("source", "local"),
        )

        # 6. Update global state
        # Sorted mode: the initial window materializes the first
        # len(queue_ids) rows of the context order, so position_in_playlist
        # (= next refill offset, see get_next_tracks invariant) starts there.
        now = time.time()
        position_in_playlist = 0 if shuffle else len(queue_ids)
        await update_state(
            {
                "current_track": queue_tracks[queue_index],
                "queue": tuple(queue_tracks),
                "queue_index": queue_index,
                "position_ms": 0,
                "track_started_at": now,
                "is_playing": True,
                "active_device_id": active_device_id,
                "current_context": request.context,
                "shuffle_enabled": shuffle,
                "sort_spec": None,
                "position_in_playlist": position_in_playlist,
                "duration_ms": 0,
                "current_history_id": history_id,
            }
        )

        # 7. Persist queue state
        save_queue_state(
            context=request.context,
            queue_ids=queue_ids,
            queue_index=queue_index,
            shuffle=shuffle,
            sort_spec=None,
            position_in_playlist=None if shuffle else position_in_playlist,
            db_conn=db,
        )

    return {
        "queue": queue_tracks,
        "queue_index": queue_index,
        "active_device_id": active_device_id,
    }


@router.post("/pause")
async def pause():
    """Pause playback on active device."""
    async with _player_lock:
        state = get_state()

        if not state.is_playing:
            return {"message": "Already paused"}

        # Accumulate listening time and update position
        elapsed_ms = 0
        if state.track_started_at:
            elapsed_ms = int((time.time() - state.track_started_at) * 1000)

        await update_state(
            {
                "duration_ms": state.duration_ms + elapsed_ms,
                "position_ms": state.position_ms + elapsed_ms,
                "is_playing": False,
                "track_started_at": None,
            }
        )

    return {"message": "Paused"}


class ResumeRequest(BaseModel):
    """Resume playback request."""

    target_device_id: str | None = None


@router.post("/resume")
async def resume(request: ResumeRequest | None = None):
    """Resume playback on specified or active device."""
    from ..sync_manager import sync_manager

    async with _player_lock:
        state = get_state()

        if state.is_playing:
            return {"message": "Already playing"}

        if not state.current_track:
            raise HTTPException(400, "No track to resume")

        # Use specified device or keep current, defaulting to first connected.
        # Stale ids (not in the connected registry) are discarded — see play().
        active_device_id = state.active_device_id
        if request and request.target_device_id:
            active_device_id = request.target_device_id
        if active_device_id and active_device_id not in sync_manager.devices:
            active_device_id = None
        if not active_device_id and sync_manager.devices:
            active_device_id = next(iter(sync_manager.devices.keys()))

        await update_state(
            {
                "is_playing": True,
                "track_started_at": time.time(),
                "active_device_id": active_device_id,
            }
        )

    return {"message": "Resumed", "active_device_id": active_device_id}


async def _restart_organizer_loop(db) -> None:
    """Re-initialize the organizer pool once it has been fully walked.

    Organizer plays a finite pool of unassigned tracks. When advance_queue runs off the
    end it clears current_track; we rebuild the whole pool fresh (dead tracks already
    filtered by initialize_queue) and start over from the top. Called ONLY at the true
    end of the queue — never mid-queue, which previously snapped playback back to
    queue[0] on every skip.

    Caller must hold _player_lock (asyncio.Lock is not reentrant — do NOT
    acquire it here).
    """
    from ..queries.tracks import batch_fetch_tracks_with_metadata
    from music_minion.domain.radio.history import start_play

    state = get_state()
    new_queue_ids = initialize_queue(
        state.current_context,
        db,
        shuffle=state.shuffle_enabled,
        sort_spec=state.sort_spec,
    )
    if not new_queue_ids:
        logger.info("Organizer loop restart: no available tracks")
        return

    new_tracks = batch_fetch_tracks_with_metadata(new_queue_ids, db)
    history_id = start_play(
        track_id=new_tracks[0]["id"],
        source_type=new_tracks[0].get("source", "local"),
    )
    await update_state(
        {
            "queue": tuple(new_tracks),
            "queue_index": 0,
            "current_track": new_tracks[0],
            "position_ms": 0,
            "track_started_at": time.time(),
            "is_playing": True,
            "current_history_id": history_id,
        }
    )
    save_queue_state(
        context=state.current_context,
        queue_ids=new_queue_ids,
        queue_index=0,
        shuffle=state.shuffle_enabled,
        sort_spec=state.sort_spec,
        db_conn=db,
    )
    logger.info(f"Organizer loop restarted: {len(new_tracks)} tracks")


@router.post("/next")
async def next_track(reason: str = "skip", db=Depends(get_db)):
    """Skip to next track.

    Args:
        reason: Why playback ended - 'skip' (default) or 'completed'
    """
    async with _player_lock:
        from ..queries.tracks import batch_fetch_tracks_with_metadata

        state = get_state()
        if not state.queue:
            raise HTTPException(400, "No queue")

        # Close current history entry
        if state.current_history_id:
            from music_minion.domain.radio.history import end_play

            final_duration = _calculate_final_duration()
            end_play(state.current_history_id, final_duration, reason=reason)

        # Reuse the request-scoped conn for the dead-track check inside advance.
        await update_state(lambda s: advance_queue(s, db))

        # Refetch state after advancement
        state = get_state()

        queue_saved = False  # whether the full queue JSON was persisted below

        # Refill / loop depending on context.
        if state.current_context and state.current_context.type == "organizer":
            # Organizer plays a fixed pool of unassigned tracks. Walk it positionally;
            # advance_queue clears current_track only when we run off the end. Rebuild a
            # fresh loop ONLY there — never mid-queue, which used to snap playback back to
            # queue[0] on every skip (the "same song over and over" bug).
            if state.current_track is None and state.queue:
                await _restart_organizer_loop(db)
                queue_saved = True
        elif state.current_track:
            # Rolling-window contexts: once fewer than REFILL_THRESHOLD tracks
            # remain ahead of the cursor, top the window back up to WINDOW_SIZE
            # in ONE batched call (instead of paying a full refill cycle of
            # queries on every single skip).
            tracks_ahead = len(state.queue) - state.queue_index
            if tracks_ahead < REFILL_THRESHOLD:
                exclusion_ids = [t["id"] for t in state.queue[state.queue_index :]]
                new_track_ids, new_position = get_next_tracks(
                    context=state.current_context,
                    count=WINDOW_SIZE - tracks_ahead,
                    exclusion_ids=exclusion_ids,
                    db_conn=db,
                    shuffle=state.shuffle_enabled,
                    sort_spec=state.sort_spec,
                    position_in_sorted=state.position_in_playlist,
                )

                new_tracks = (
                    batch_fetch_tracks_with_metadata(
                        new_track_ids, db, preserve_order=True
                    )
                    if new_track_ids
                    else []
                )

                updates: dict = {}
                if new_tracks:
                    updates["queue"] = state.queue + tuple(new_tracks)
                # Sorted mode: always advance the cursor by rows fetched (even
                # if every fetched row was excluded) so it can't stall.
                if (
                    new_position is not None
                    and new_position != state.position_in_playlist
                ):
                    updates["position_in_playlist"] = new_position

                if updates:
                    await update_state(updates)
                    state = get_state()

                if new_tracks:
                    save_queue_state(
                        context=state.current_context,
                        queue_ids=[t["id"] for t in state.queue],
                        queue_index=state.queue_index,
                        shuffle=state.shuffle_enabled,
                        sort_spec=state.sort_spec,
                        position_in_playlist=None
                        if state.shuffle_enabled
                        else state.position_in_playlist,
                        db_conn=db,
                    )
                    queue_saved = True

        if not queue_saved:
            # Queue contents unchanged — persist just the cursor (cheap UPDATE,
            # no full queue-ID JSON reserialize) so a restart resumes in place.
            state = get_state()
            update_queue_position(
                state.queue_index,
                None if state.shuffle_enabled else state.position_in_playlist,
                db,
            )

        return {"status": "next"}


@router.post("/prev")
async def prev_track():
    """Go to previous track."""
    async with _player_lock:
        state = get_state()

        if not state.queue:
            raise HTTPException(400, "No queue")

        # If more than 3 seconds in, restart current track
        if state.position_ms > 3000:
            await update_state(
                {
                    "position_ms": 0,
                    "track_started_at": time.time() if state.is_playing else None,
                }
            )
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
                    source_type=state.queue[new_index].get("source", "local"),
                )

                await update_state(
                    {
                        "queue_index": new_index,
                        "current_track": state.queue[new_index],
                        "position_ms": 0,
                        "track_started_at": time.time() if state.is_playing else None,
                        "duration_ms": 0,
                        "current_history_id": history_id,
                    }
                )
            else:
                # At start of queue, just restart current track
                await update_state(
                    {
                        "position_ms": 0,
                        "track_started_at": time.time() if state.is_playing else None,
                    }
                )

    return {"message": "Previous track"}


@router.post("/seek")
async def seek(request: SeekRequest):
    """Seek to position in current track."""
    async with _player_lock:
        state = get_state()

        if not state.current_track:
            raise HTTPException(400, "No track playing")

        # Accumulate listening time before seeking
        elapsed_ms = 0
        if state.track_started_at:
            elapsed_ms = int((time.time() - state.track_started_at) * 1000)

        await update_state(
            {
                "duration_ms": state.duration_ms + elapsed_ms,
                "position_ms": request.position_ms,
                "track_started_at": time.time() if state.is_playing else None,
            }
        )

    return {"message": "Seeked"}


@router.post("/toggle-shuffle")
async def toggle_shuffle(db=Depends(get_db)):
    """Toggle shuffle without interrupting playback."""
    from ..queries.tracks import batch_fetch_tracks_with_metadata

    async with _player_lock:
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
            sort_spec=sort_spec,
        )

        # Fetch full track metadata
        new_queue = batch_fetch_tracks_with_metadata(
            new_queue_ids, db, preserve_order=True
        )

        # Sorted mode: the rebuilt window consumed roughly the first
        # len(new_queue_ids) rows of the sorted order (see get_next_tracks
        # invariant); the next refill reads from there.
        position_in_playlist = 0 if new_shuffle else len(new_queue_ids)

        await update_state(
            {
                "queue": tuple(new_queue),
                "shuffle_enabled": new_shuffle,
                "sort_spec": sort_spec,
                "position_in_playlist": position_in_playlist,
            }
        )

        # Persist state
        save_queue_state(
            context=state.current_context,
            queue_ids=new_queue_ids,
            queue_index=state.queue_index,
            shuffle=new_shuffle,
            sort_spec=sort_spec,
            position_in_playlist=None if new_shuffle else position_in_playlist,
            db_conn=db,
        )

    return {"shuffle_enabled": new_shuffle, "queue_size": len(new_queue)}


@router.post("/set-sort")
async def set_sort(request: SetSortRequest, db=Depends(get_db)):
    """Apply manual table sort (disables shuffle)."""
    from ..queries.tracks import batch_fetch_tracks_with_metadata

    async with _player_lock:
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
            sort_spec=sort_spec,
        )

        new_queue = batch_fetch_tracks_with_metadata(
            new_queue_ids, db, preserve_order=True
        )

        await update_state(
            {
                "shuffle_enabled": False,
                "sort_spec": sort_spec,
                # Next refill offset = rows of the sorted order materialized in
                # the rebuilt window (was hardcoded 100 regardless of size).
                "position_in_playlist": len(new_queue_ids),
                "queue": tuple(new_queue),
            }
        )

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
            db_conn=db,
        )

    return {"queue_size": len(new_queue), "sort": sort_spec}


class TransferRequest(BaseModel):
    """Request to transfer playback to a different device."""

    device_id: str


@router.post("/transfer")
async def transfer_playback(request: TransferRequest):
    """Transfer playback to a different device."""
    from ..sync_manager import sync_manager

    async with _player_lock:
        # Verify device exists
        if request.device_id not in sync_manager.devices:
            raise HTTPException(400, f"Device {request.device_id} not connected")

        await update_state({"active_device_id": request.device_id})

    return {"active_device_id": request.device_id}


@router.get("/state")
async def get_player_state():
    """Get current playback state."""
    return get_playback_state()


@router.get("/queue")
async def get_player_queue(offset: int = 0, limit: int = 100):
    """Get one page of the live queue.

    playback:state broadcasts are slim (no queue array); clients call this
    when the broadcast queueVersion moves past the version they hold.
    Returns {version, total, offset, tracks}.
    """
    return get_queue_page(offset=offset, limit=limit)


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
                    cursor = db.execute(
                        "SELECT id FROM playlists WHERE id = ?", (context.playlist_id,)
                    )
                    if not cursor.fetchone():
                        logger.warning(
                            f"Saved queue referenced deleted playlist {context.playlist_id}, clearing queue"
                        )
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

            await update_state(
                {
                    "queue": tuple(queue_tracks),
                    "queue_index": state["queue_index"],
                    "shuffle_enabled": state["shuffle_enabled"],
                    "sort_spec": state.get("sort_spec"),
                    "position_in_playlist": state.get("position_in_playlist", 0),
                    "current_context": state["context"],
                    "current_track": current_track,
                    "is_playing": False,  # Don't auto-resume
                },
                broadcast=False,
            )  # No clients connected at startup

            logger.info("Queue state restored successfully")
    except Exception:
        logger.exception("Failed to restore queue state, starting with clean state")
