from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
import uuid
from ..deps import get_db
from ..schemas import (
    StartSessionRequest,
    StartSessionResponse,
    RecordComparisonRequest,
    RecordComparisonResponse,
    ComparisonPair,
    TrackInfo,
)
from music_minion.domain.rating.database import (
    get_filtered_tracks,
    get_or_create_rating,
    record_comparison,
)
from music_minion.domain.rating.elo import (
    select_strategic_pair,
    select_weighted_pair,
    update_ratings,
    get_k_factor,
)

router = APIRouter()


def _track_to_info(track: dict) -> TrackInfo:
    """Convert a track dict to TrackInfo schema."""
    return TrackInfo(
        id=track["id"],
        title=track["title"],
        artist=track["artist"],
        album=track["album"],
        year=track["year"],
        bpm=track["bpm"],
        genre=track["genre"],
        rating=track["rating"],
        comparison_count=track["comparison_count"],
        wins=track.get("wins", 0),
        losses=track["comparison_count"] - track.get("wins", 0),
        duration=track["duration"],
        has_waveform=False,  # TODO: implement waveform check
    )


def _select_pair(
    tracks: list[dict],
    ratings_cache: dict,
    priority_path_prefix: Optional[str],
    exclude_track_ids: Optional[set[int]] = None,
) -> tuple[dict, dict]:
    """Select a pair using strategic or weighted pairing."""
    if exclude_track_ids:
        tracks = [t for t in tracks if t["id"] not in exclude_track_ids]
        ratings_cache = {k: v for k, v in ratings_cache.items() if k not in exclude_track_ids}

    if len(tracks) < 2:
        raise ValueError("Not enough tracks for comparison")

    if priority_path_prefix:
        priority_tracks = [t for t in tracks if t.get("local_path", "").startswith(priority_path_prefix)]
        if priority_tracks:
            return select_weighted_pair(tracks, priority_tracks, ratings_cache)

    return select_strategic_pair(tracks, ratings_cache)


@router.post("/comparisons/session", response_model=StartSessionResponse)
async def start_comparison_session(
    request: StartSessionRequest,
) -> StartSessionResponse:
    """Start a new comparison session with filtered tracks."""
    try:
        # Get filtered tracks based on request parameters
        tracks = get_filtered_tracks(
            genre=request.genre_filter,
            year=int(request.year_filter)
            if request.year_filter and request.year_filter.isdigit()
            else None,
            playlist_id=request.playlist_id,
            source_filter=request.source_filter,
        )

        if len(tracks) < 2:
            raise HTTPException(
                status_code=400, detail="Not enough tracks available for comparison"
            )

        # Create ratings cache for strategic pairing
        ratings_cache = {
            track["id"]: {
                "rating": track["rating"],
                "comparison_count": track["comparison_count"],
            }
            for track in tracks
        }

        session_id = str(uuid.uuid4())

        # Select first pair
        track_a, track_b = _select_pair(tracks, ratings_cache, request.priority_path_prefix)
        current_pair = ComparisonPair(
            track_a=_track_to_info(track_a),
            track_b=_track_to_info(track_b),
            session_id=session_id,
        )

        # Prefetch next pair (excluding current tracks for variety)
        prefetched_pair = None
        if len(tracks) >= 4:
            try:
                exclude_ids = {track_a["id"], track_b["id"]}
                pf_a, pf_b = _select_pair(tracks, ratings_cache, request.priority_path_prefix, exclude_ids)
                prefetched_pair = ComparisonPair(
                    track_a=_track_to_info(pf_a),
                    track_b=_track_to_info(pf_b),
                    session_id=session_id,
                )
            except ValueError:
                pass  # Not enough tracks for prefetch, that's fine

        return StartSessionResponse(
            session_id=session_id,
            total_tracks=len(tracks),
            pair=current_pair,
            prefetched_pair=prefetched_pair,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _get_pair_with_prefetch(
    session_id: str,
    priority_path_prefix: Optional[str] = None,
    exclude_track_ids: Optional[set[int]] = None,
) -> tuple[ComparisonPair, Optional[ComparisonPair]]:
    """Get a comparison pair and prefetch the next one."""
    tracks = get_filtered_tracks()

    if len(tracks) < 2:
        raise ValueError("Not enough tracks available for comparison")

    ratings_cache = {
        track["id"]: {
            "rating": track["rating"],
            "comparison_count": track["comparison_count"],
        }
        for track in tracks
    }

    # Select current pair
    track_a, track_b = _select_pair(tracks, ratings_cache, priority_path_prefix, exclude_track_ids)
    current_pair = ComparisonPair(
        track_a=_track_to_info(track_a),
        track_b=_track_to_info(track_b),
        session_id=session_id,
    )

    # Prefetch next pair
    prefetched_pair = None
    current_ids = exclude_track_ids or set()
    next_exclude = current_ids | {track_a["id"], track_b["id"]}
    if len(tracks) >= len(next_exclude) + 2:
        try:
            pf_a, pf_b = _select_pair(tracks, ratings_cache, priority_path_prefix, next_exclude)
            prefetched_pair = ComparisonPair(
                track_a=_track_to_info(pf_a),
                track_b=_track_to_info(pf_b),
                session_id=session_id,
            )
        except ValueError:
            pass

    return current_pair, prefetched_pair


@router.get("/comparisons/next-pair", response_model=ComparisonPair)
async def get_next_comparison_pair(
    session_id: str, priority_path_prefix: Optional[str] = None
) -> ComparisonPair:
    """Get the next comparison pair for a session."""
    try:
        pair, _ = _get_pair_with_prefetch(session_id, priority_path_prefix)
        return pair
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/comparisons/record", response_model=RecordComparisonResponse)
async def record_comparison_result(
    request: RecordComparisonRequest,
) -> RecordComparisonResponse:
    """Record a comparison result and return the next pair with prefetch."""
    try:
        # Get ratings for both tracks
        rating_a = get_or_create_rating(request.track_a_id)
        rating_b = get_or_create_rating(request.track_b_id)

        # Determine winner and loser
        if request.winner_id == request.track_a_id:
            winner_rating = rating_a
            loser_rating = rating_b
            winner_side = "a"
        elif request.winner_id == request.track_b_id:
            winner_rating = rating_b
            loser_rating = rating_a
            winner_side = "b"
        else:
            raise HTTPException(
                status_code=400, detail="Winner ID must be one of the track IDs"
            )

        # Update ratings
        k_factor = get_k_factor(winner_rating.comparison_count)
        new_winner_rating, new_loser_rating = update_ratings(
            winner_rating.rating, loser_rating.rating, k_factor
        )

        # Record the comparison
        record_comparison(
            track_a_id=request.track_a_id,
            track_b_id=request.track_b_id,
            winner_id=request.winner_id,
            track_a_rating_before=winner_rating.rating
            if winner_side == "a"
            else loser_rating.rating,
            track_b_rating_before=loser_rating.rating
            if winner_side == "a"
            else winner_rating.rating,
            track_a_rating_after=new_winner_rating
            if winner_side == "a"
            else new_loser_rating,
            track_b_rating_after=new_loser_rating
            if winner_side == "a"
            else new_winner_rating,
            session_id=request.session_id,
        )

        # Get next pair with prefetch
        next_pair, prefetched_pair = _get_pair_with_prefetch(
            request.session_id, request.priority_path_prefix
        )

        return RecordComparisonResponse(
            success=True,
            comparisons_done=1,
            next_pair=next_pair,
            prefetched_pair=prefetched_pair,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
