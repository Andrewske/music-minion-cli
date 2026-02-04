from fastapi import APIRouter, HTTPException
from typing import List, Optional
from ..deps import get_db
from ..schemas import (
    CreatePlaylistRequest,
    PlaylistStatsResponse,
    PlaylistTrackEntry,
    PlaylistTracksResponse,
)

router = APIRouter()


def get_playlist_tracks_with_ratings(playlist_id: int) -> List[dict]:
    """Get all tracks in a playlist with their ratings, wins, and losses.

    Handles both manual playlists (from playlist_tracks table) and
    smart playlists (dynamically evaluated from filters).
    """
    from music_minion.core.database import get_db_connection
    from music_minion.domain.playlists import get_playlist_by_id
    from music_minion.domain.playlists.filters import evaluate_filters

    # Check if this is a smart playlist
    playlist = get_playlist_by_id(playlist_id)
    if not playlist:
        return []

    if playlist["type"] == "smart":
        # Smart playlist - use filter evaluation
        tracks = evaluate_filters(playlist_id)
        # Transform to match expected format with rating data
        return [
            {
                "id": t["id"],
                "title": t["title"],
                "artist": t["artist"],
                "rating": t.get("playlist_elo_rating", 1500.0),
                "comparison_count": t.get("playlist_elo_comparison_count", 0),
                "wins": t.get("playlist_elo_wins", 0),
                "losses": t.get("playlist_elo_comparison_count", 0) - t.get("playlist_elo_wins", 0),
            }
            for t in tracks
        ]

    # Manual playlist - query from playlist_tracks table
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            SELECT
                t.id,
                t.title,
                t.artist,
                COALESCE(per.rating, 1500.0) as rating,
                COALESCE(per.comparison_count, 0) as comparison_count,
                COALESCE(per.wins, 0) as wins,
                COALESCE(per.comparison_count - per.wins, 0) as losses
            FROM playlist_tracks pt
            JOIN tracks t ON pt.track_id = t.id
            LEFT JOIN playlist_elo_ratings per ON pt.track_id = per.track_id
                AND per.playlist_id = pt.playlist_id
            WHERE pt.playlist_id = ?
            ORDER BY COALESCE(per.rating, 1500.0) DESC, t.title ASC
            """,
            (playlist_id,),
        )

        return [dict(row) for row in cursor.fetchall()]


def get_playlist_name(playlist_id: int) -> Optional[str]:
    """Get playlist name by ID."""
    from music_minion.core.database import get_db_connection

    with get_db_connection() as conn:
        cursor = conn.execute(
            "SELECT name FROM playlists WHERE id = ?",
            (playlist_id,),
        )
        row = cursor.fetchone()
        return row["name"] if row else None


@router.get("/playlists")
async def get_playlists():
    """Get all playlists for the current user."""
    try:
        from music_minion.core.database import get_db_connection
        from music_minion.domain.playlists.crud import get_all_playlists

        playlists = get_all_playlists()
        return {"playlists": playlists}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get playlists: {str(e)}"
        )


@router.post("/playlists")
async def create_playlist(request: CreatePlaylistRequest):
    """Create a new manual playlist."""
    try:
        from music_minion.domain.playlists.crud import create_playlist as create_playlist_fn

        # Create playlist in active library
        playlist_id = create_playlist_fn(
            name=request.name,
            playlist_type="manual",
            description=request.description
        )

        # Get created playlist data
        from music_minion.core.database import get_db_connection
        with get_db_connection() as conn:
            cursor = conn.execute(
                "SELECT id, name, type, description, track_count, library FROM playlists WHERE id = ?",
                (playlist_id,)
            )
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=500, detail="Created playlist but failed to fetch")
            playlist = dict(row)

        return playlist
    except ValueError as e:
        # Handle duplicate name error
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create playlist: {str(e)}")


@router.get("/playlists/{playlist_id}/stats", response_model=PlaylistStatsResponse)
async def get_playlist_stats(playlist_id: int):
    """Get statistics for a specific playlist."""
    try:
        from music_minion.domain.playlists.analytics import get_playlist_analytics

        analytics = get_playlist_analytics(playlist_id)
        if "error" in analytics:
            raise HTTPException(status_code=404, detail=analytics["error"])

        # Transform analytics data to match PlaylistStatsResponse schema
        return PlaylistStatsResponse(
            playlist_name=analytics["playlist_name"],
            playlist_type=analytics["playlist_type"],
            basic=analytics["basic"],
            elo=analytics["elo"],
            quality=analytics["quality"],
            top_artists=analytics["artists"]["top_artists"],
            top_genres=analytics["genres"]["genres"],
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get playlist stats: {str(e)}"
        )


@router.get("/playlists/{playlist_id}/tracks", response_model=PlaylistTracksResponse)
async def get_playlist_tracks(playlist_id: int):
    """Get all tracks in a playlist with their ratings, wins, and losses."""
    try:
        # Check if playlist exists
        playlist_name = get_playlist_name(playlist_id)
        if not playlist_name:
            raise HTTPException(status_code=404, detail="Playlist not found")

        # Get tracks with ratings
        tracks_data = get_playlist_tracks_with_ratings(playlist_id)

        # Transform to response model
        tracks = [
            PlaylistTrackEntry(
                id=track["id"],
                title=track["title"],
                artist=track["artist"],
                rating=round(float(track["rating"]), 2),
                wins=track["wins"],
                losses=track["losses"],
                comparison_count=track["comparison_count"],
            )
            for track in tracks_data
        ]

        return PlaylistTracksResponse(
            playlist_name=playlist_name,
            tracks=tracks,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get playlist tracks: {str(e)}"
        )
