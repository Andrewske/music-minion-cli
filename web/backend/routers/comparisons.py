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
)
from music_minion.domain.rating.database import (
    get_filtered_tracks,
    get_or_create_rating,
    record_comparison,
)
from music_minion.domain.rating.elo import (
    select_strategic_pair,
    update_ratings,
    get_k_factor,
)

router = APIRouter()


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

        # Generate session ID
        session_id = str(uuid.uuid4())

        # Select strategic pair
        track_a, track_b = select_strategic_pair(tracks, ratings_cache)

        # Convert to response format
        response_pair = ComparisonPair(
            track_a={
                "id": track_a["id"],
                "title": track_a["title"],
                "artist": track_a["artist"],
                "album": track_a["album"],
                "year": track_a["year"],
                "bpm": track_a["bpm"],
                "genre": track_a["genre"],
                "rating": track_a["rating"],
                "comparison_count": track_a["comparison_count"],
                "wins": track_a.get("wins", 0),
                "losses": track_a["comparison_count"] - track_a.get("wins", 0),
                "duration": track_a["duration"],
                "has_waveform": False,  # TODO: implement waveform check
            },
            track_b={
                "id": track_b["id"],
                "title": track_b["title"],
                "artist": track_b["artist"],
                "album": track_b["album"],
                "year": track_b["year"],
                "bpm": track_b["bpm"],
                "genre": track_b["genre"],
                "rating": track_b["rating"],
                "comparison_count": track_b["comparison_count"],
                "wins": track_b.get("wins", 0),
                "losses": track_b["comparison_count"] - track_b.get("wins", 0),
                "duration": track_b["duration"],
                "has_waveform": False,  # TODO: implement waveform check
            },
            session_id=session_id,
        )

        return StartSessionResponse(
            session_id=session_id,
            total_tracks=len(tracks),
            pair=response_pair,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/comparisons/next-pair", response_model=ComparisonPair)
async def get_next_comparison_pair(session_id: str) -> ComparisonPair:
    """Get the next comparison pair for a session."""
    # For now, return a random pair - TODO: implement session tracking
    tracks = get_filtered_tracks()

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

    track_a, track_b = select_strategic_pair(tracks, ratings_cache)

    return ComparisonPair(
        track_a={
            "id": track_a["id"],
            "title": track_a["title"],
            "artist": track_a["artist"],
            "album": track_a["album"],
            "year": track_a["year"],
            "bpm": track_a["bpm"],
            "genre": track_a["genre"],
            "rating": track_a["rating"],
            "comparison_count": track_a["comparison_count"],
            "wins": track_a.get("wins", 0),
            "losses": track_a["comparison_count"] - track_a.get("wins", 0),
            "duration": track_a["duration"],
            "has_waveform": False,
        },
        track_b={
            "id": track_b["id"],
            "title": track_b["title"],
            "artist": track_b["artist"],
            "album": track_b["album"],
            "year": track_b["year"],
            "bpm": track_b["bpm"],
            "genre": track_b["genre"],
            "rating": track_b["rating"],
            "comparison_count": track_b["comparison_count"],
            "wins": track_b.get("wins", 0),
            "losses": track_b["comparison_count"] - track_b.get("wins", 0),
            "duration": track_b["duration"],
            "has_waveform": False,
        },
        session_id=session_id,
    )


@router.post("/comparisons/record", response_model=RecordComparisonResponse)
async def record_comparison_result(
    request: RecordComparisonRequest,
) -> RecordComparisonResponse:
    """Record a comparison result and return the next pair."""
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

        # Get next pair (session continues until user closes browser/navigates away)
        next_pair = await get_next_comparison_pair(request.session_id)

        return RecordComparisonResponse(
            success=True,
            comparisons_done=1,  # Single comparison recorded
            next_pair=next_pair,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
