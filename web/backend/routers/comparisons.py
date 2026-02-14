from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
import uuid
from pydantic import BaseModel
from ..deps import get_db
from ..sync_manager import sync_manager
from ..schemas import (
    StartSessionRequest,
    StartSessionResponse,
    RecordComparisonRequest,
    RecordComparisonResponse,
    ComparisonPair,
    TrackInfo,
)
from ..queries.emojis import batch_fetch_track_emojis
from music_minion.ipc import send_command
from music_minion.domain.rating.database import (
    get_filtered_tracks,
    get_or_create_rating,
    get_or_create_playlist_rating,
    record_comparison,
    record_playlist_comparison,
    create_playlist_ranking_session,
    get_playlist_ranking_session,
    update_playlist_ranking_session,
)
from music_minion.domain.rating.elo import (
    select_strategic_pair,
    select_weighted_pair,
    update_ratings,
    get_k_factor,
)

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


def _make_pair(track_a: dict, track_b: dict, session_id: str) -> ComparisonPair:
    """Create a ComparisonPair with batch-fetched emojis.

    Args:
        track_a: First track dictionary
        track_b: Second track dictionary
        session_id: Session identifier

    Returns:
        ComparisonPair with emojis populated for both tracks
    """
    from music_minion.core.database import get_db_connection

    with get_db_connection() as conn:
        emojis_map = batch_fetch_track_emojis([track_a["id"], track_b["id"]], conn)

    return ComparisonPair(
        track_a=_track_to_info(track_a, emojis_map.get(track_a["id"], [])),
        track_b=_track_to_info(track_b, emojis_map.get(track_b["id"], [])),
        session_id=session_id,
    )


def _select_pair(
    tracks: list[dict],
    ratings_cache: dict,
    priority_path_prefix: Optional[str],
    exclude_track_ids: Optional[set[int]] = None,
) -> tuple[dict, dict]:
    """Select a pair using strategic or weighted pairing."""
    import logging

    logger = logging.getLogger(__name__)

    logger.debug(
        f"_select_pair called with {len(tracks)} tracks, ratings_cache keys: {list(ratings_cache.keys())[:5]}..."
    )

    if exclude_track_ids:
        logger.debug(f"Excluding track IDs: {exclude_track_ids}")
        tracks = [t for t in tracks if t["id"] not in exclude_track_ids]
        ratings_cache = {
            k: v for k, v in ratings_cache.items() if k not in exclude_track_ids
        }
        logger.debug(f"After exclusion: {len(tracks)} tracks remaining")

    if len(tracks) < 2:
        logger.error("Not enough tracks for comparison")
        raise ValueError("Not enough tracks for comparison")

    if priority_path_prefix:
        priority_tracks = [
            t
            for t in tracks
            if t.get("local_path", "").startswith(priority_path_prefix)
        ]
        if priority_tracks:
            logger.debug(
                f"Using weighted pairing with {len(priority_tracks)} priority tracks"
            )
            return select_weighted_pair(tracks, priority_tracks, ratings_cache)

    logger.debug("Using strategic pairing")
    result = select_strategic_pair(tracks, ratings_cache)
    logger.debug(f"Selected pair: {result[0]['title']} vs {result[1]['title']}")
    return result


@router.post("/comparisons/session", response_model=StartSessionResponse)
async def start_comparison_session(
    request: StartSessionRequest, db=Depends(get_db)
) -> StartSessionResponse:
    """Start a new comparison session with filtered tracks."""
    import logging

    logger = logging.getLogger(__name__)

    try:
        logger.info(f"Starting comparison session with request: {request.dict()}")
        session_id = str(uuid.uuid4())

        if request.ranking_mode == "playlist" and request.playlist_id:
            # Playlist ranking mode
            logger.info(
                f"Starting playlist ranking session for playlist {request.playlist_id}"
            )
            conn = db
            cursor = conn.execute(
                """
                SELECT
                    t.id, t.title, t.artist, t.album, t.genre, t.year,
                    t.local_path, t.soundcloud_id, t.spotify_id, t.youtube_id, t.source,
                    COALESCE(per.rating, 1500.0) as playlist_rating,
                    COALESCE(per.comparison_count, 0) as playlist_comparison_count,
                    COALESCE(per.wins, 0) as playlist_wins,
                    COALESCE(er.rating, 1500.0) as global_rating
                FROM playlist_tracks pt
                JOIN tracks t ON pt.track_id = t.id
                LEFT JOIN playlist_elo_ratings per ON t.id = per.track_id AND per.playlist_id = ?
                LEFT JOIN elo_ratings er ON t.id = er.track_id
                WHERE pt.playlist_id = ?
                ORDER BY pt.position
            """,
                (request.playlist_id, request.playlist_id),
            )

            logger.info(f"Executed playlist query for playlist {request.playlist_id}")

            tracks = []
            for row in cursor.fetchall():
                track = dict(row)
                track["rating"] = track[
                    "playlist_rating"
                ]  # Use playlist rating as primary
                track["comparison_count"] = track["playlist_comparison_count"]
                track["wins"] = track["playlist_wins"]
                track["losses"] = (
                    track["playlist_comparison_count"] - track["playlist_wins"]
                )
                tracks.append(track)

            logger.info(f"Loaded {len(tracks)} tracks for playlist ranking")

            if len(tracks) < 2:
                raise HTTPException(
                    status_code=400, detail="Not enough tracks in playlist for ranking"
                )

            # Create or resume playlist ranking session
            existing_session = get_playlist_ranking_session(request.playlist_id)
            if existing_session:
                logger.info(
                    f"Resuming existing playlist ranking session for playlist {request.playlist_id}"
                )
                session_id = existing_session["session_id"]
                # Update session with new total if tracks changed
                import json

                progress_stats = json.loads(existing_session["progress_stats"])
                if progress_stats.get("total") != len(tracks):
                    update_playlist_ranking_session(
                        request.playlist_id,
                        compared_count=progress_stats.get("compared", 0),
                    )
            else:
                logger.info(
                    f"Creating new playlist ranking session for playlist {request.playlist_id}"
                )
                create_playlist_ranking_session(
                    request.playlist_id, session_id, len(tracks)
                )
                logger.info("Playlist ranking session created successfully")

            # Create ratings cache for strategic pairing (use playlist ratings)
            ratings_cache = {
                track["id"]: {
                    "rating": track["playlist_rating"],
                    "comparison_count": track["playlist_comparison_count"],
                }
                for track in tracks
            }

        else:
            # Standard global ranking mode
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

        # Select first pair
        logger.info("Selecting first pair for comparison session")
        track_a, track_b = _select_pair(
            tracks, ratings_cache, request.priority_path_prefix
        )
        logger.info(
            f"Pair selected successfully: {track_a['title']} vs {track_b['title']}"
        )

        current_pair = _make_pair(track_a, track_b, session_id)

        logger.info("ComparisonPair created successfully")

        # Prefetch next pair (excluding current tracks for variety)
        prefetched_pair = None
        if len(tracks) >= 4:
            try:
                exclude_ids = {track_a["id"], track_b["id"]}
                pf_a, pf_b = _select_pair(
                    tracks, ratings_cache, request.priority_path_prefix, exclude_ids
                )
                prefetched_pair = _make_pair(pf_a, pf_b, session_id)
            except ValueError:
                pass  # Not enough tracks for prefetch, that's fine

        # Activate comparison mode in CLI context for web-winner hotkey
        logger.info("Activating comparison mode in CLI context")
        ipc_success, ipc_message = send_command("set-web-mode", ["comparison"])
        if not ipc_success:
            logger.warning(f"Failed to activate comparison mode: {ipc_message}")

        logger.info(
            f"Returning StartSessionResponse with session_id={session_id}, total_tracks={len(tracks)}"
        )

        # Store initial state for reconnecting clients (e.g., phone joining desktop session)
        sync_manager.set_comparison_state(
            current_pair.dict(),
            prefetched_pair.dict() if prefetched_pair else None,
            session_id=session_id,
        )

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
    track_a, track_b = _select_pair(
        tracks, ratings_cache, priority_path_prefix, exclude_track_ids
    )
    current_pair = _make_pair(track_a, track_b, session_id)

    # Prefetch next pair
    prefetched_pair = None
    current_ids = exclude_track_ids or set()
    next_exclude = current_ids | {track_a["id"], track_b["id"]}
    if len(tracks) >= len(next_exclude) + 2:
        try:
            pf_a, pf_b = _select_pair(
                tracks, ratings_cache, priority_path_prefix, next_exclude
            )
            prefetched_pair = _make_pair(pf_a, pf_b, session_id)
        except ValueError:
            pass

    return current_pair, prefetched_pair


def _get_playlist_pair_with_prefetch(
    playlist_id: int,
    session_id: str,
    priority_path_prefix: Optional[str] = None,
    exclude_track_ids: Optional[set[int]] = None,
) -> tuple[ComparisonPair, Optional[ComparisonPair]]:
    """Get a comparison pair and prefetch the next one for playlist ranking."""
    # Get playlist tracks with ratings
    from music_minion.core.database import get_db_connection

    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            SELECT
                t.id, t.title, t.artist, t.album, t.genre, t.year,
                t.local_path, t.soundcloud_id, t.spotify_id, t.youtube_id, t.source,
                COALESCE(per.rating, 1500.0) as playlist_rating,
                COALESCE(per.comparison_count, 0) as playlist_comparison_count,
                COALESCE(per.wins, 0) as playlist_wins,
                COALESCE(er.rating, 1500.0) as global_rating
            FROM playlist_tracks pt
            JOIN tracks t ON pt.track_id = t.id
            LEFT JOIN playlist_elo_ratings per ON t.id = per.track_id AND per.playlist_id = ?
            LEFT JOIN elo_ratings er ON t.id = er.track_id
            WHERE pt.playlist_id = ?
            ORDER BY pt.position
            """,
            (playlist_id, playlist_id),
        )

        tracks = []
        for row in cursor.fetchall():
            track = dict(row)
            track["rating"] = track["playlist_rating"]  # Use playlist rating as primary
            track["comparison_count"] = track["playlist_comparison_count"]
            track["wins"] = track["playlist_wins"]
            track["losses"] = (
                track["playlist_comparison_count"] - track["playlist_wins"]
            )
            tracks.append(track)

    if len(tracks) < 2:
        raise ValueError("Not enough tracks in playlist for comparison")

    ratings_cache = {
        track["id"]: {
            "rating": track["playlist_rating"],
            "comparison_count": track["playlist_comparison_count"],
        }
        for track in tracks
    }

    # Select current pair
    track_a, track_b = _select_pair(
        tracks, ratings_cache, priority_path_prefix, exclude_track_ids
    )
    current_pair = _make_pair(track_a, track_b, session_id)

    # Prefetch next pair
    prefetched_pair = None
    current_ids = exclude_track_ids or set()
    next_exclude = current_ids | {track_a["id"], track_b["id"]}
    if len(tracks) >= len(next_exclude) + 2:
        try:
            pf_a, pf_b = _select_pair(
                tracks, ratings_cache, priority_path_prefix, next_exclude
            )
            prefetched_pair = _make_pair(pf_a, pf_b, session_id)
        except ValueError:
            # Not enough tracks for prefetch, that's OK
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
    request: RecordComparisonRequest, db=Depends(get_db)
) -> RecordComparisonResponse:
    """Record a comparison result and return the next pair with prefetch."""
    import logging

    logger = logging.getLogger(__name__)

    logger.info(
        f"recordComparison received: ranking_mode={request.ranking_mode}, playlist_id={request.playlist_id}"
    )

    try:
        # Get global ratings (always needed)
        rating_a_global = get_or_create_rating(request.track_a_id)
        rating_b_global = get_or_create_rating(request.track_b_id)

        if request.ranking_mode == "playlist" and request.playlist_id:
            # Playlist ranking mode
            rating_a_playlist = get_or_create_playlist_rating(
                str(request.track_a_id), request.playlist_id
            )
            rating_b_playlist = get_or_create_playlist_rating(
                str(request.track_b_id), request.playlist_id
            )

            # Use playlist ratings for Elo calculation
            rating_a = rating_a_playlist
            rating_b = rating_b_playlist
        else:
            # Standard global ranking mode
            rating_a = rating_a_global
            rating_b = rating_b_global

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
        if request.ranking_mode == "playlist" and request.playlist_id:
            # Playlist ranking mode
            record_playlist_comparison(
                track_a_id=str(request.track_a_id),
                track_b_id=str(request.track_b_id),
                winner_id=str(request.winner_id),
                playlist_id=request.playlist_id,
                track_a_playlist_rating_before=rating_a.rating
                if winner_side == "a"
                else rating_b.rating,
                track_b_playlist_rating_before=rating_b.rating
                if winner_side == "a"
                else rating_a.rating,
                track_a_playlist_rating_after=new_winner_rating
                if winner_side == "a"
                else new_loser_rating,
                track_b_playlist_rating_after=new_loser_rating
                if winner_side == "a"
                else new_winner_rating,
                track_a_global_rating_before=rating_a_global.rating,
                track_b_global_rating_before=rating_b_global.rating,
                track_a_global_rating_after=rating_a_global.rating,  # No change
                track_b_global_rating_after=rating_b_global.rating,  # No change
                session_id=request.session_id,
            )
        else:
            # Standard global ranking mode
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
        if request.ranking_mode == "playlist" and request.playlist_id:
            # Playlist mode: get next pair from playlist tracks
            logger.info(f"Getting next pair for playlist {request.playlist_id}")
            next_pair, prefetched_pair = _get_playlist_pair_with_prefetch(
                request.playlist_id,
                request.session_id,
                request.priority_path_prefix,
                exclude_track_ids={request.track_a_id, request.track_b_id},
            )
        else:
            # Global mode: get next pair from global tracks
            next_pair, prefetched_pair = _get_pair_with_prefetch(
                request.session_id,
                request.priority_path_prefix,
                exclude_track_ids={request.track_a_id, request.track_b_id},
            )

        # Update stored state for reconnecting clients
        sync_manager.set_comparison_state(
            next_pair.dict(),
            prefetched_pair.dict() if prefetched_pair else None,
            session_id=request.session_id,
        )

        # Broadcast to all connected clients
        await sync_manager.broadcast("comparison:advanced", {
            "pair": next_pair.dict(),
            "prefetched": prefetched_pair.dict() if prefetched_pair else None,
            "session_id": request.session_id,
        })

        return RecordComparisonResponse(
            success=True,
            comparisons_done=1,
            next_pair=next_pair,
            prefetched_pair=prefetched_pair,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class TrackSelectionRequest(BaseModel):
    track_id: int | str  # int from frontend, "track_a"/"track_b" from CLI
    is_playing: bool


@router.post("/comparisons/select-track")
async def select_track(request: TrackSelectionRequest):
    """Broadcast track selection to all clients."""
    track_id = request.track_id

    # Resolve CLI aliases to actual track IDs
    if isinstance(track_id, str):
        current = sync_manager.current_comparison
        if not current or not current.get("pair"):
            return {"status": "error", "message": "No active comparison"}
        if track_id == "track_a":
            track_id = current["pair"]["track_a"]["id"]
            track_info = current["pair"]["track_a"]
        elif track_id == "track_b":
            track_id = current["pair"]["track_b"]["id"]
            track_info = current["pair"]["track_b"]
        else:
            return {"status": "error", "message": f"Unknown track alias: {track_id}"}
    else:
        # Look up track info from current comparison pair
        current = sync_manager.current_comparison
        if current and current.get("pair"):
            pair = current["pair"]
            if pair["track_a"]["id"] == track_id:
                track_info = pair["track_a"]
            elif pair["track_b"]["id"] == track_id:
                track_info = pair["track_b"]
            else:
                track_info = {"id": track_id}  # Fallback
        else:
            track_info = {"id": track_id}

    # Broadcast full track object (not just ID)
    await sync_manager.broadcast("comparison:track_selected", {
        "track": track_info,
        "isPlaying": request.is_playing,
    })
    return {"status": "ok"}
