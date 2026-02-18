"""Playlist builder domain logic with pure functions.

Provides core functionality for the web-based playlist builder:
- Filter management (separate from smart playlist filters)
- Candidate track selection with exclusions
- Skip/add operations
- Session persistence
"""

import sqlite3
from datetime import datetime
from typing import Any, Optional

from loguru import logger

from music_minion.core.database import get_db_connection
from .filters import build_filter_query, validate_filter
from .crud import add_track_to_playlist as add_track_to_playlist_crud


# Filter Management


def get_builder_filters(playlist_id: int) -> list[dict]:
    """Get builder filters for a playlist.

    Args:
        playlist_id: Playlist ID

    Returns:
        List of filter dictionaries with keys: id, field, operator, value, conjunction
    """
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            SELECT id, field, operator, value, conjunction
            FROM playlist_builder_filters
            WHERE playlist_id = ?
            ORDER BY id
            """,
            (playlist_id,),
        )
        return [dict(row) for row in cursor.fetchall()]


def set_builder_filters(playlist_id: int, filters: list[dict]) -> None:
    """Atomically replace all builder filters for a playlist.

    Args:
        playlist_id: Playlist ID
        filters: List of filter dicts with keys: field, operator, value, conjunction

    Raises:
        ValueError: If any filter is invalid
    """
    # Validate all filters first
    for f in filters:
        validate_filter(f["field"], f["operator"], f["value"])
        if f.get("conjunction", "AND") not in ("AND", "OR"):
            raise ValueError(f"Invalid conjunction: {f.get('conjunction')}")

    with get_db_connection() as conn:
        # Delete existing filters
        conn.execute(
            "DELETE FROM playlist_builder_filters WHERE playlist_id = ?",
            (playlist_id,),
        )

        # Insert new filters
        if filters:
            conn.executemany(
                """
                INSERT INTO playlist_builder_filters
                (playlist_id, field, operator, value, conjunction)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        playlist_id,
                        f["field"],
                        f["operator"],
                        f["value"],
                        f.get("conjunction", "AND"),
                    )
                    for f in filters
                ],
            )

        conn.commit()


def clear_builder_filters(playlist_id: int) -> None:
    """Remove all builder filters for a playlist.

    Args:
        playlist_id: Playlist ID
    """
    with get_db_connection() as conn:
        conn.execute(
            "DELETE FROM playlist_builder_filters WHERE playlist_id = ?",
            (playlist_id,),
        )
        conn.commit()


# Candidate Selection


def get_candidate_tracks(
    playlist_id: int,
    sort_field: str = "artist",
    sort_direction: str = "asc",
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """Get paginated candidate tracks with server-side sorting.

    Returns tracks that:
    - Match builder filters (if any set)
    - Are NOT already in the playlist
    - Are NOT in the skipped list
    - Are NOT archived

    Args:
        playlist_id: Playlist ID
        sort_field: Column to sort by (artist, title, year, bpm, genre, key_signature, elo_rating)
        sort_direction: 'asc' or 'desc'
        limit: Tracks per page (default 100)
        offset: Number of tracks to skip

    Returns:
        Tuple of (tracks list, total count)
    """
    # Validate sort_field against allowlist to prevent SQL injection
    ALLOWED_SORT_FIELDS = {
        "artist",
        "title",
        "year",
        "bpm",
        "genre",
        "key_signature",
        "elo_rating",
    }
    if sort_field not in ALLOWED_SORT_FIELDS:
        sort_field = "artist"

    # Map elo_rating to the computed column
    order_column = (
        "COALESCE(er.rating, 1500.0)" if sort_field == "elo_rating" else f"t.{sort_field}"
    )
    order_dir = "DESC" if sort_direction == "desc" else "ASC"

    # Get builder filters
    filters = get_builder_filters(playlist_id)

    # Build WHERE clause for filters
    filter_where = ""
    filter_params = []
    if filters:
        filter_where, filter_params = build_filter_query(filters)
        filter_where = f"({filter_where}) AND "

    # Query with NOT EXISTS optimization for better performance
    with get_db_connection() as conn:
        # First get total count (without LIMIT/OFFSET)
        count_query = f"""
            SELECT COUNT(DISTINCT t.id)
            FROM tracks t
            WHERE {filter_where}
                t.local_path IS NOT NULL AND t.local_path != ''
                AND NOT EXISTS (
                    SELECT 1 FROM playlist_tracks
                    WHERE playlist_id = ? AND track_id = t.id
                )
                AND NOT EXISTS (
                    SELECT 1 FROM playlist_builder_skipped
                    WHERE playlist_id = ? AND track_id = t.id
                )
                AND NOT EXISTS (
                    SELECT 1 FROM ratings
                    WHERE rating_type = 'archive' AND track_id = t.id
                )
        """

        cursor = conn.execute(
            count_query,
            tuple(filter_params) + (playlist_id, playlist_id),
        )
        total_count = cursor.fetchone()[0]

        # Then get paginated results
        query = f"""
            SELECT DISTINCT
                t.*
            FROM tracks t
            WHERE {filter_where}
                t.local_path IS NOT NULL AND t.local_path != ''
                AND NOT EXISTS (
                    SELECT 1 FROM playlist_tracks
                    WHERE playlist_id = ? AND track_id = t.id
                )
                AND NOT EXISTS (
                    SELECT 1 FROM playlist_builder_skipped
                    WHERE playlist_id = ? AND track_id = t.id
                )
                AND NOT EXISTS (
                    SELECT 1 FROM ratings
                    WHERE rating_type = 'archive' AND track_id = t.id
                )
            ORDER BY {order_column} {order_dir} NULLS LAST, t.id ASC
            LIMIT ? OFFSET ?
        """

        cursor = conn.execute(
            query,
            tuple(filter_params) + (playlist_id, playlist_id, limit, offset),
        )
        tracks = [dict(row) for row in cursor.fetchall()]

        return (tracks, total_count)


def get_next_candidate(
    playlist_id: int, exclude_track_id: Optional[int] = None
) -> Optional[dict]:
    """Get next random candidate track for the session.

    Excludes the last processed track for variety.
    Returns None if no candidates available.

    Args:
        playlist_id: Playlist ID
        exclude_track_id: Track ID to exclude (typically last processed)

    Returns:
        Track dict or None
    """
    # Get all candidates (first page, random order)
    candidates, _ = get_candidate_tracks(playlist_id, sort_field="artist", sort_direction="asc", limit=100, offset=0)

    # Filter out excluded track
    if exclude_track_id is not None:
        candidates = [c for c in candidates if c["id"] != exclude_track_id]

    # Return random candidate
    if candidates:
        import random

        return random.choice(candidates)

    return None


# Skip/Add Operations


def skip_track(playlist_id: int, track_id: int) -> dict:
    """Mark track as skipped and persist to database.

    CRITICAL: Must INSERT into playlist_builder_skipped table
    so broken tracks don't reappear in future sessions.

    Args:
        playlist_id: Playlist ID
        track_id: Track ID to skip

    Returns:
        Dict with keys: skipped_track_id, success
    """
    try:
        with get_db_connection() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO playlist_builder_skipped
                (playlist_id, track_id)
                VALUES (?, ?)
                """,
                (playlist_id, track_id),
            )
            conn.commit()

        return {"skipped_track_id": track_id, "success": True}

    except sqlite3.Error as e:
        logger.exception(f"Failed to skip track {track_id} for playlist {playlist_id}")
        return {"skipped_track_id": track_id, "success": False}


def add_track(playlist_id: int, track_id: int) -> dict:
    """Add track to playlist using existing CRUD.

    Args:
        playlist_id: Playlist ID
        track_id: Track ID to add

    Returns:
        Dict with keys: added_track_id, success
    """
    try:
        success = add_track_to_playlist_crud(playlist_id, track_id)
        return {"added_track_id": track_id, "success": success}

    except Exception as e:
        logger.exception(f"Failed to add track {track_id} to playlist {playlist_id}")
        return {"added_track_id": track_id, "success": False}


def unskip_track(playlist_id: int, track_id: int) -> None:
    """Remove track from skipped list.

    Args:
        playlist_id: Playlist ID
        track_id: Track ID to unskip

    Raises:
        sqlite3.Error: If database operation fails
    """
    with get_db_connection() as conn:
        conn.execute(
            """
            DELETE FROM playlist_builder_skipped
            WHERE playlist_id = ? AND track_id = ?
            """,
            (playlist_id, track_id),
        )
        conn.commit()


def get_skipped_tracks(playlist_id: int) -> list[dict]:
    """Get all skipped tracks for a playlist (for review UI).

    Args:
        playlist_id: Playlist ID

    Returns:
        List of track dictionaries with skip metadata
    """
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            SELECT
                t.*,
                s.skipped_at
            FROM playlist_builder_skipped s
            JOIN tracks t ON s.track_id = t.id
            WHERE s.playlist_id = ?
            ORDER BY s.skipped_at DESC
            """,
            (playlist_id,),
        )
        return [dict(row) for row in cursor.fetchall()]


# Session Management


def start_builder_session(playlist_id: int) -> dict:
    """Create or resume builder session.

    Note: Does NOT return current track. Frontend calls get_next_candidate() separately.

    Args:
        playlist_id: Playlist ID

    Returns:
        Dict with keys: session_id, playlist_id, started_at, updated_at

    Raises:
        sqlite3.Error: If database operation fails
    """
    with get_db_connection() as conn:
        # Check if session exists
        cursor = conn.execute(
            """
            SELECT id, playlist_id, started_at, updated_at
            FROM playlist_builder_sessions
            WHERE playlist_id = ?
            """,
            (playlist_id,),
        )
        row = cursor.fetchone()

        if row:
            # Resume existing session - update timestamp
            now = datetime.now().isoformat()
            conn.execute(
                """
                UPDATE playlist_builder_sessions
                SET updated_at = ?
                WHERE playlist_id = ?
                """,
                (now, playlist_id),
            )
            conn.commit()

            return {
                "session_id": row["id"],
                "playlist_id": row["playlist_id"],
                "started_at": row["started_at"],
                "updated_at": now,
            }
        else:
            # Create new session
            now = datetime.now().isoformat()
            cursor = conn.execute(
                """
                INSERT INTO playlist_builder_sessions
                (playlist_id, started_at, updated_at)
                VALUES (?, ?, ?)
                """,
                (playlist_id, now, now),
            )
            conn.commit()

            return {
                "session_id": cursor.lastrowid,
                "playlist_id": playlist_id,
                "started_at": now,
                "updated_at": now,
            }


def get_active_session(playlist_id: int) -> Optional[dict]:
    """Get active builder session for playlist.

    Returns session metadata (no current track - computed fresh each time).

    Args:
        playlist_id: Playlist ID

    Returns:
        Session dict or None if no active session
    """
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            SELECT id, playlist_id, last_processed_track_id, started_at, updated_at
            FROM playlist_builder_sessions
            WHERE playlist_id = ?
            """,
            (playlist_id,),
        )
        row = cursor.fetchone()

        if row:
            return dict(row)

        return None


def end_builder_session(playlist_id: int) -> None:
    """Clean up builder session.

    Args:
        playlist_id: Playlist ID

    Raises:
        sqlite3.Error: If database operation fails
    """
    with get_db_connection() as conn:
        conn.execute(
            """
            DELETE FROM playlist_builder_sessions
            WHERE playlist_id = ?
            """,
            (playlist_id,),
        )
        conn.commit()


def update_last_processed_track(playlist_id: int, track_id: int) -> None:
    """Update session's last processed track ID.

    Used to exclude recently-seen tracks from next candidate selection.

    Args:
        playlist_id: Playlist ID
        track_id: Last processed track ID

    Raises:
        sqlite3.Error: If database operation fails
    """
    with get_db_connection() as conn:
        now = datetime.now().isoformat()
        conn.execute(
            """
            UPDATE playlist_builder_sessions
            SET last_processed_track_id = ?, updated_at = ?
            WHERE playlist_id = ?
            """,
            (track_id, now, playlist_id),
        )
        conn.commit()
