from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from pydantic import BaseModel
from ..deps import get_db
from ..sync_manager import sync_manager
from ..schemas import (
    ComparisonRequest,
    ComparisonResponse,
    RecordComparisonRequest,
    ComparisonPair,
    ComparisonProgress,
    TrackInfo,
)
from ..queries.emojis import batch_fetch_track_emojis
from music_minion.domain.rating.database import (
    get_next_playlist_pair,
    get_playlist_comparison_progress,
    get_playlist_elo_rating,
    record_playlist_comparison,
    RankingComplete,
)
from music_minion.domain.rating.elo import update_ratings

router = APIRouter()


def _track_to_info(track: dict, emojis: list[str] | None = None) -> TrackInfo:
    """Convert a track dict to TrackInfo schema.

    Args:
        track: Track dictionary from database
        emojis: Pre-fetched emojis (use batch_fetch_track_emojis for efficiency)
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
        )
        logger.debug(f"Converted track {track['id']} to TrackInfo")
        return track_info
    except Exception as e:
        logger.error(f"Failed to convert track to TrackInfo: {e}, track data: {track}")
        raise


def _make_pair(track_a: dict, track_b: dict) -> ComparisonPair:
    """Create a ComparisonPair with batch-fetched emojis.

    Args:
        track_a: First track dictionary
        track_b: Second track dictionary

    Returns:
        ComparisonPair with emojis populated for both tracks
    """
    from music_minion.core.database import get_db_connection

    with get_db_connection() as conn:
        emojis_map = batch_fetch_track_emojis([track_a["id"], track_b["id"]], conn)

    return ComparisonPair(
        track_a=_track_to_info(track_a, emojis_map.get(track_a["id"], [])),
        track_b=_track_to_info(track_b, emojis_map.get(track_b["id"], [])),
    )


@router.post("/comparisons/start")
async def start_comparison(
    request: ComparisonRequest,
    db=Depends(get_db)
) -> ComparisonResponse:
    """Start comparison mode for a playlist (stateless).

    No session creation, no caching - just queries next uncompared pair.
    Returns current pair + progress.
    """
    import logging
    logger = logging.getLogger(__name__)

    try:
        # Query for next pair (stateless, no cache check)
        try:
            track_a, track_b = get_next_playlist_pair(request.playlist_id)
            pair = _make_pair(track_a, track_b)
        except RankingComplete:
            # Not an error - return response with null pair to indicate completion
            pair = None
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        # Get progress
        progress_dict = get_playlist_comparison_progress(request.playlist_id)
        progress = ComparisonProgress(
            compared=progress_dict["compared"],
            total=progress_dict["total"],
            percentage=progress_dict["percentage"]
        )

        return ComparisonResponse(
            pair=pair,
            progress=progress,
        )

    except HTTPException:
        raise
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
        else:
            track_b_new, track_a_new = update_ratings(
                track_b_rating, track_a_rating, k_factor
            )

        # Record comparison (no session_id, single transaction)
        record_playlist_comparison(
            playlist_id=request.playlist_id,
            track_a_id=str(request.track_a_id),
            track_b_id=str(request.track_b_id),
            winner_id=str(request.winner_id),
            track_a_rating_before=track_a_rating,
            track_b_rating_before=track_b_rating,
            track_a_rating_after=track_a_new,
            track_b_rating_after=track_b_new,
            session_id="",  # Empty string for sessionless
        )

        # Get next pair (stateless)
        try:
            track_a, track_b = get_next_playlist_pair(request.playlist_id)
            next_pair = _make_pair(track_a, track_b)
        except RankingComplete:
            next_pair = None  # Ranking complete

        progress_dict = get_playlist_comparison_progress(request.playlist_id)
        progress = ComparisonProgress(
            compared=progress_dict["compared"],
            total=progress_dict["total"],
            percentage=progress_dict["percentage"]
        )

        # Broadcast update to all connected devices
        await sync_manager.broadcast_comparison_update(
            request.playlist_id,
            progress_dict
        )

        return ComparisonResponse(
            pair=next_pair,
            progress=progress,
        )

    except Exception as e:
        logger.exception("Failed to record comparison")
        raise HTTPException(status_code=500, detail=str(e))


