from fastapi import APIRouter, Depends, HTTPException
from ..deps import get_db
from music_minion.ipc import send_command
from ..sync_manager import sync_manager
from ..schemas import (
    ComparisonRequest,
    ComparisonResponse,
    RecordComparisonRequest,
    UndoComparisonRequest,
    ComparisonPair,
    ComparisonProgress,
    TrackInfo,
)
from ..queries.emojis import batch_fetch_track_emojis
from ..queries.track_details import fetch_banner_details
from .playlists import clear_playlist_tracks_cache
from music_minion.domain.rating.database import (
    get_next_playlist_pair,
    get_playlist_pair,
    get_playlist_comparison_progress,
    get_playlist_elo_rating,
    record_playlist_comparison,
    undo_playlist_comparison,
    RankingComplete,
)
from music_minion.domain.rating.elo import update_ratings

router = APIRouter()


def _track_to_info(
    track: dict, emojis: list[str] | None = None, details: dict | None = None
) -> TrackInfo:
    """Convert a track dict to TrackInfo schema.

    Args:
        track: Track dictionary from database
        emojis: Pre-fetched emojis (use batch_fetch_track_emojis for efficiency)
        details: Banner details from fetch_banner_details (key, date, SC link...)
    """
    import logging

    logger = logging.getLogger(__name__)

    try:
        wins = track.get("wins", 0) or 0
        track_info = TrackInfo(
            id=track["id"],
            title=track["title"],
            artist=track["artist"],
            album=track["album"],
            year=track["year"],
            bpm=track.get("bpm"),
            genre=track["genre"],
            rating=float(track["rating"]),
            comparison_count=int(track["comparison_count"]),
            wins=int(wins),
            losses=int(track["comparison_count"]) - int(wins),
            duration=track.get("duration"),
            has_waveform=False,  # TODO: implement waveform check
            emojis=emojis or [],
            playlist_rating=track.get("playlist_rating"),
            playlist_comparison_count=track.get("playlist_comparison_count"),
            global_rating=track.get("global_rating"),
            source=track.get("source"),
            local_path=track.get("local_path"),
            artwork_url=track.get("artwork_url"),
            **(details or {}),
        )
        logger.debug(f"Converted track {track['id']} to TrackInfo")
        return track_info
    except Exception as e:
        logger.error(f"Failed to convert track to TrackInfo: {e}, track data: {track}")
        raise


def _make_pair(track_a: dict, track_b: dict, playlist_id: int) -> ComparisonPair:
    """Create a ComparisonPair with batch-fetched emojis and banner details."""
    from music_minion.core.database import get_db_connection

    ids = [track_a["id"], track_b["id"]]
    with get_db_connection() as conn:
        emojis_map = batch_fetch_track_emojis(ids, conn)
        details_map = fetch_banner_details(conn, playlist_id, ids)

    def info(track: dict) -> TrackInfo:
        tid = track["id"]
        return _track_to_info(track, emojis_map.get(tid, []), details_map.get(tid))

    return ComparisonPair(track_a=info(track_a), track_b=info(track_b))


def _next_pair(playlist_id: int) -> ComparisonPair | None:
    """The next pair to compare, or None when ranking is complete."""
    try:
        track_a, track_b = get_next_playlist_pair(playlist_id)
    except RankingComplete:
        return None
    return _make_pair(track_a, track_b, playlist_id)


def _progress(playlist_id: int) -> ComparisonProgress:
    progress_dict = get_playlist_comparison_progress(playlist_id)
    return ComparisonProgress(
        compared=progress_dict["compared"],
        total=progress_dict["total"],
        percentage=progress_dict["percentage"],
    )


@router.post("/comparisons/start")
async def start_comparison(
    request: ComparisonRequest,
    db=Depends(get_db)
) -> ComparisonResponse:
    """Start comparison mode for a playlist (stateless).

    No session creation, no caching - just queries next uncompared pair.
    Returns current pair (None when ranking is complete) + progress.
    """
    import logging
    logger = logging.getLogger(__name__)

    try:
        pair = _next_pair(request.playlist_id)
        return ComparisonResponse(pair=pair, progress=_progress(request.playlist_id))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Failed to start comparison for playlist {request.playlist_id}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/comparisons/record")
async def record_comparison(
    request: RecordComparisonRequest,
    db=Depends(get_db)
) -> ComparisonResponse:
    """Record a comparison result (no session_id needed).

    Always playlist-based. After recording, gets next pair.
    """
    import logging
    logger = logging.getLogger(__name__)

    try:
        # Get current ratings
        track_a_rating = get_playlist_elo_rating(request.track_a_id, request.playlist_id)
        track_b_rating = get_playlist_elo_rating(request.track_b_id, request.playlist_id)

        # Calculate new ratings
        k_factor = 32
        if request.winner_id == request.track_a_id:
            track_a_new, track_b_new = update_ratings(
                track_a_rating, track_b_rating, k_factor
            )
            rating_delta = track_a_new - track_a_rating
        else:
            track_b_new, track_a_new = update_ratings(
                track_b_rating, track_a_rating, k_factor
            )
            rating_delta = track_b_new - track_b_rating

        # Record comparison (no session_id, single transaction)
        comparison_id = record_playlist_comparison(
            playlist_id=request.playlist_id,
            track_a_id=request.track_a_id,
            track_b_id=request.track_b_id,
            winner_id=request.winner_id,
            track_a_rating_before=track_a_rating,
            track_b_rating_before=track_b_rating,
            track_a_rating_after=track_a_new,
            track_b_rating_after=track_b_new,
            session_id="",  # Empty string for sessionless
        )
        clear_playlist_tracks_cache()

        next_pair = _next_pair(request.playlist_id)
        progress = _progress(request.playlist_id)

        # Broadcast update to all connected devices
        await sync_manager.broadcast_comparison_update(
            request.playlist_id, progress.model_dump()
        )

        return ComparisonResponse(
            pair=next_pair,
            progress=progress,
            comparison_id=comparison_id,
            rating_delta=rating_delta,
        )

    except Exception as e:
        logger.exception("Failed to record comparison")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/comparisons/undo")
async def undo_comparison(request: UndoComparisonRequest) -> ComparisonResponse:
    """Delete one recorded comparison, restore both ratings, and return that pair.

    409 when the comparison isn't in this playlist, a later comparison
    involves either track, or either rating changed since (e.g. organizer
    "Apply rating"). If a track has left the playlist, returns the next pair.
    """
    import logging
    logger = logging.getLogger(__name__)

    try:
        undone = undo_playlist_comparison(request.playlist_id, request.comparison_id)
    except Exception as e:
        logger.exception(f"Failed to undo comparison {request}")
        raise HTTPException(status_code=500, detail=str(e))
    if undone is None:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot undo comparison {request.comparison_id} in playlist "
            f"{request.playlist_id}: not found, or a later comparison or rating "
            "change involves these tracks",
        )
    clear_playlist_tracks_cache()
    restored = get_playlist_pair(request.playlist_id, *undone)
    try:
        pair = (
            _make_pair(*restored, request.playlist_id)
            if restored
            else _next_pair(request.playlist_id)
        )
    except ValueError:  # fewer than two tracks left in the playlist
        pair = None
    progress = _progress(request.playlist_id)
    await sync_manager.broadcast_comparison_update(
        request.playlist_id, progress.model_dump()
    )
    return ComparisonResponse(pair=pair, progress=progress)


# Context Activation Endpoints


@router.post("/comparisons/activate")
async def activate_comparison_mode():
    """Activate comparison mode in CLI context.

    Sends IPC command to set active_web_mode='comparison' so that
    web-winner/web-archive hotkeys work correctly.
    """
    import logging
    log = logging.getLogger(__name__)
    log.info("activate_comparison_mode called")

    try:
        log.info("Sending IPC command: set-web-mode comparison")
        success, message = send_command("set-web-mode", ["comparison"])
        log.info(f"IPC response: success={success}, message={message}")

        if not success:
            raise HTTPException(status_code=500, detail=f"Failed to activate: {message}")

        return {"success": True}

    except HTTPException:
        raise
    except Exception as e:
        log.exception("Failed to activate comparison mode")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/comparisons/activate")
async def deactivate_comparison_mode():
    """Deactivate comparison mode in CLI context.

    Sends IPC command to clear active_web_mode.
    Called when leaving the comparison page.
    """
    try:
        success, message = send_command("set-web-mode", ["none"])

        # Don't fail hard - CLI might have restarted
        return {"success": True}

    except Exception:
        # Swallow errors on deactivation - not critical
        return {"success": True}

