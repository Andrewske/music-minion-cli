from fastapi import APIRouter, HTTPException
from typing import List, Optional
from ..deps import get_db
from ..schemas import (
    CreatePlaylistRequest,
    Filter,
    FilterResponse,
    SmartFiltersResponse,
    PlaylistStatsResponse,
    PlaylistTrackEntry,
    PlaylistTracksResponse,
)

router = APIRouter()


def get_playlist_tracks_with_ratings(
    playlist_id: int,
    sort_field: str = "artist",
    sort_direction: str = "asc"
) -> List[dict]:
    """Get all tracks in a playlist with their ratings, wins, and losses.

    Handles both manual playlists (from playlist_tracks table) and
    smart playlists (dynamically evaluated from filters).

    Args:
        playlist_id: ID of the playlist
        sort_field: Field to sort by (artist, title, album, year, bpm, etc.)
        sort_direction: Sort direction ('asc' or 'desc')
    """
    from music_minion.core.database import get_db_connection
    from music_minion.domain.playlists import get_playlist_by_id
    from music_minion.domain.playlists.filters import evaluate_filters

    # Check if this is a smart playlist
    playlist = get_playlist_by_id(playlist_id)
    if not playlist:
        return []

    # Validate and map sort field to column name
    field_mapping = {
        "artist": "artist",
        "title": "title",
        "album": "album",
        "genre": "genre",
        "year": "year",
        "bpm": "bpm",
        "key": "key_signature",
        "rating": "rating",
    }
    column = field_mapping.get(sort_field, "artist")
    direction = "DESC" if sort_direction.lower() == "desc" else "ASC"

    if playlist["type"] == "smart":
        # Smart playlist - use filter evaluation with extended fields
        tracks = evaluate_filters(playlist_id)

        # Transform to match expected format with full track fields
        result = [
            {
                "id": t["id"],
                "title": t["title"],
                "artist": t["artist"],
                "album": t.get("album"),
                "genre": t.get("genre"),
                "year": t.get("year"),
                "bpm": t.get("bpm"),
                "key_signature": t.get("key_signature"),
                "elo_rating": t.get("playlist_elo_rating", 1500.0),
                "rating": t.get("playlist_elo_rating", 1500.0),
                "comparison_count": t.get("playlist_elo_comparison_count", 0),
                "wins": t.get("playlist_elo_wins", 0),
                "losses": t.get("playlist_elo_comparison_count", 0) - t.get("playlist_elo_wins", 0),
            }
            for t in tracks
        ]

        # Apply sorting (Python-side since evaluate_filters returns all tracks)
        result.sort(
            key=lambda x: (x.get(sort_field) or "", x.get("artist") or ""),
            reverse=(direction == "DESC")
        )
        return result

    # Manual playlist - query from playlist_tracks table
    with get_db_connection() as conn:
        # SQL injection safe: column and direction validated via whitelist above
        query = f"""
            SELECT
                t.id,
                t.title,
                t.artist,
                t.album,
                t.genre,
                t.year,
                t.bpm,
                t.key_signature,
                COALESCE(per.rating, 1500.0) as rating,
                COALESCE(per.rating, 1500.0) as elo_rating,
                COALESCE(per.comparison_count, 0) as comparison_count,
                COALESCE(per.wins, 0) as wins,
                COALESCE(per.comparison_count - per.wins, 0) as losses
            FROM playlist_tracks pt
            JOIN tracks t ON pt.track_id = t.id
            LEFT JOIN playlist_elo_ratings per ON pt.track_id = per.track_id
                AND per.playlist_id = pt.playlist_id
            WHERE pt.playlist_id = ?
            ORDER BY {column} {direction}, t.title ASC
        """
        cursor = conn.execute(query, (playlist_id,))
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


@router.get("/playlists/{playlist_id}/tracks")
async def get_playlist_tracks(
    playlist_id: int,
    sort_field: str = "artist",
    sort_direction: str = "asc"
):
    """Get all tracks in a playlist with their ratings, wins, and losses.

    For smart playlists, returns full track metadata including:
    album, genre, year, bpm, key_signature, elo_rating

    Args:
        playlist_id: ID of the playlist
        sort_field: Field to sort by (artist, title, album, year, bpm, key, rating)
        sort_direction: Sort direction ('asc' or 'desc')
    """
    try:
        # Check if playlist exists
        playlist_name = get_playlist_name(playlist_id)
        if not playlist_name:
            raise HTTPException(status_code=404, detail="Playlist not found")

        # Get tracks with ratings (with sorting)
        tracks_data = get_playlist_tracks_with_ratings(
            playlist_id,
            sort_field=sort_field,
            sort_direction=sort_direction
        )

        # Return raw track data (includes all fields for smart playlists)
        return {
            "playlist_name": playlist_name,
            "tracks": tracks_data,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get playlist tracks: {str(e)}"
        )


@router.get("/playlists/{playlist_id}/filters", response_model=SmartFiltersResponse)
async def get_smart_filters(playlist_id: int):
    """Get filters for a smart playlist."""
    try:
        from music_minion.domain.playlists import get_playlist_by_id
        from music_minion.domain.playlists.filters import get_playlist_filters

        # Verify playlist exists
        playlist = get_playlist_by_id(playlist_id)
        if not playlist:
            raise HTTPException(status_code=404, detail="Playlist not found")

        # Get filters (returns empty list if no filters)
        filters_data = get_playlist_filters(playlist_id)

        # Transform to FilterResponse models
        filters = [
            FilterResponse(
                id=f["id"],
                field=f["field"],
                operator=f["operator"],
                value=f["value"],
                conjunction=f["conjunction"],
            )
            for f in filters_data
        ]

        return SmartFiltersResponse(filters=filters)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get filters: {str(e)}"
        )


@router.put("/playlists/{playlist_id}/filters", response_model=SmartFiltersResponse)
async def update_smart_filters(playlist_id: int, filters: List[Filter]):
    """Replace all filters for a smart playlist (atomic operation)."""
    try:
        from music_minion.core.database import get_db_connection
        from music_minion.domain.playlists import get_playlist_by_id
        from music_minion.domain.playlists.filters import validate_filter, get_playlist_filters

        # 1. Verify playlist exists and is type='smart'
        playlist = get_playlist_by_id(playlist_id)
        if not playlist:
            raise HTTPException(status_code=404, detail="Playlist not found")

        if playlist["type"] != "smart":
            raise HTTPException(
                status_code=400,
                detail="Cannot add filters to manual playlist. Only smart playlists support filters."
            )

        # 2. Validate ALL filters first (fail fast before any DB writes)
        for f in filters:
            try:
                validate_filter(f.field, f.operator, f.value)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

            if f.conjunction not in ("AND", "OR"):
                raise HTTPException(
                    status_code=400,
                    detail=f"Conjunction must be 'AND' or 'OR', got: {f.conjunction}"
                )

        # 3. Atomic replace: DELETE + INSERT in single transaction
        with get_db_connection() as conn:
            try:
                # Delete all existing filters
                conn.execute(
                    "DELETE FROM playlist_filters WHERE playlist_id = ?",
                    (playlist_id,)
                )

                # Insert new filters via executemany
                if filters:
                    filter_data = [
                        (playlist_id, f.field, f.operator, f.value, f.conjunction)
                        for f in filters
                    ]
                    conn.executemany(
                        """
                        INSERT INTO playlist_filters (playlist_id, field, operator, value, conjunction)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        filter_data
                    )

                conn.commit()
            except Exception as e:
                conn.rollback()
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to update filters (rolled back): {str(e)}"
                )

        # 4. Return updated filters
        updated_filters = get_playlist_filters(playlist_id)
        filters_response = [
            FilterResponse(
                id=f["id"],
                field=f["field"],
                operator=f["operator"],
                value=f["value"],
                conjunction=f["conjunction"],
            )
            for f in updated_filters
        ]

        return SmartFiltersResponse(filters=filters_response)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to update filters: {str(e)}"
        )
