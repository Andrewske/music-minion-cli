"""
Playlist management for Music Minion CLI
Functional approach with explicit state passing
"""

import json
from typing import Any, Optional

from loguru import logger

from music_minion.core.database import get_db_connection

from . import filters, sync


def create_playlist(
    name: str, playlist_type: str, description: Optional[str] = None
) -> int:
    """
    Create a new playlist in the current active library.

    If active library is SoundCloud/Spotify, automatically creates a remote playlist
    and links it to the local playlist.

    Args:
        name: Playlist name (must be unique within library)
        playlist_type: 'manual' or 'smart'
        description: Optional description

    Returns:
        Playlist ID

    Raises:
        ValueError: If playlist name already exists in this library or type is invalid
    """
    if playlist_type not in ["manual", "smart"]:
        raise ValueError(
            f"Invalid playlist type: {playlist_type}. Must be 'manual' or 'smart'"
        )

    # Get active library to assign playlist to it
    active_library = sync.get_active_library()

    with get_db_connection() as conn:
        try:
            cursor = conn.execute(
                """
                INSERT INTO playlists (name, type, description, library)
                VALUES (?, ?, ?, ?)
            """,
                (name, playlist_type, description, active_library),
            )
            conn.commit()
            playlist_id = cursor.lastrowid
        except Exception as e:
            if "UNIQUE constraint failed" in str(e):
                raise ValueError(
                    f"Playlist '{name}' already exists in {active_library} library"
                )
            raise

    # If active library is SoundCloud, create remote playlist and link it
    if active_library == "soundcloud":
        logger.info(
            f"Active library is SoundCloud, creating remote playlist for '{name}'"
        )
        success, soundcloud_id, error = sync._ensure_soundcloud_playlist_linked(
            playlist_id, name
        )
        if not success:
            logger.warning(f"Failed to create SoundCloud playlist: {error}")
            # Don't fail - local playlist was created successfully

    return playlist_id


def update_playlist_track_count(playlist_id: int) -> None:
    """
    Update the track_count field for a playlist.
    For manual playlists, counts rows in playlist_tracks.
    For smart playlists, evaluates filters and counts matching tracks.

    Args:
        playlist_id: ID of playlist to update
    """
    playlist = get_playlist_by_id(playlist_id)
    if not playlist:
        return

    with get_db_connection() as conn:
        # Begin explicit transaction for atomicity
        conn.execute("BEGIN")
        try:
            if playlist["type"] == "manual":
                # Count tracks in playlist_tracks table
                cursor = conn.execute(
                    """
                    SELECT COUNT(*) as count
                    FROM playlist_tracks
                    WHERE playlist_id = ?
                """,
                    (playlist_id,),
                )
                count = cursor.fetchone()["count"]
            else:
                # Smart playlist - evaluate filters
                matching_tracks = filters.evaluate_filters(playlist_id)
                count = len(matching_tracks)

            conn.execute(
                """
                UPDATE playlists
                SET track_count = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """,
                (count, playlist_id),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def delete_playlist(playlist_id: int) -> bool:
    """
    Delete a playlist and all associated data.

    Args:
        playlist_id: ID of playlist to delete

    Returns:
        True if playlist was deleted, False if not found
    """
    with get_db_connection() as conn:
        # Begin explicit transaction for atomicity
        conn.execute("BEGIN")
        try:
            # Clear active playlist entry if this is active (CASCADE handles this via FK constraint)
            # No manual deletion needed - FK ON DELETE SET NULL will handle it

            # Delete playlist (CASCADE will handle playlist_tracks and filters)
            cursor = conn.execute("DELETE FROM playlists WHERE id = ?", (playlist_id,))
            deleted = cursor.rowcount > 0

            conn.commit()
            return deleted
        except Exception:
            conn.rollback()
            raise


def rename_playlist(playlist_id: int, new_name: str) -> bool:
    """
    Rename a playlist.

    Args:
        playlist_id: ID of playlist to rename
        new_name: New name for the playlist

    Returns:
        True if renamed successfully, False if playlist not found

    Raises:
        ValueError: If new name already exists
    """
    with get_db_connection() as conn:
        try:
            cursor = conn.execute(
                """
                UPDATE playlists
                SET name = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """,
                (new_name, playlist_id),
            )
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            if "UNIQUE constraint failed" in str(e):
                raise ValueError(f"Playlist '{new_name}' already exists")
            raise


def reorder_playlist_by_elo(playlist_id: int) -> bool:
    """
    Reorder tracks in a playlist by their playlist-specific ELO ratings.

    Highest rated tracks get lowest position numbers (appear first).
    Only works for manual playlists.

    Args:
        playlist_id: Playlist ID to reorder

    Returns:
        True if reordering was successful, False if playlist not found or not manual

    Raises:
        Exception: If database operation fails
    """
    with get_db_connection() as conn:
        # Check if playlist exists and is manual
        cursor = conn.execute(
            "SELECT type FROM playlists WHERE id = ?",
            (playlist_id,),
        )
        row = cursor.fetchone()
        if not row or row["type"] != "manual":
            logger.warning(f"Playlist {playlist_id} not found or not a manual playlist")
            return False

        # Get tracks with their playlist ratings, ordered by rating descending
        cursor = conn.execute(
            """
            SELECT pt.track_id, COALESCE(per.rating, 1500.0) as playlist_rating
            FROM playlist_tracks pt
            LEFT JOIN playlist_elo_ratings per ON pt.track_id = per.track_id
                AND per.playlist_id = ?
            WHERE pt.playlist_id = ?
            ORDER BY playlist_rating DESC, per.comparison_count DESC
        """,
            (playlist_id, playlist_id),
        )

        tracks = cursor.fetchall()
        if not tracks:
            logger.info(f"No tracks found in playlist {playlist_id}")
            return True

        # Update positions based on rating order
        for position, track in enumerate(tracks, 1):
            conn.execute(
                """
                UPDATE playlist_tracks
                SET position = ?
                WHERE playlist_id = ? AND track_id = ?
            """,
                (position, playlist_id, track["track_id"]),
            )

        conn.commit()
        logger.info(
            f"Reordered {len(tracks)} tracks in playlist {playlist_id} by ELO rating"
        )
        return True


def get_all_playlists(library: Optional[str] = None) -> list[dict[str, Any]]:
    """
    Get all playlists with metadata for the active library.

    Args:
        library: Library to filter by. If None, uses active library from database.

    Returns:
        List of playlist dicts with id, name, type, description, created_at, updated_at, track_count
    """
    with get_db_connection() as conn:
        # Get active library if not specified
        if library is None:
            library = sync.get_active_library()

        cursor = conn.execute(
            """
            SELECT
                id,
                name,
                type,
                description,
                track_count,
                created_at,
                updated_at,
                last_played_at,
                library
            FROM playlists
            WHERE library = ?
            ORDER BY name
        """,
            (library,),
        )
        return [dict(row) for row in cursor.fetchall()]


def get_playlists_sorted_by_recent(
    library: Optional[str] = None,
) -> list[dict[str, Any]]:
    """
    Get all playlists sorted by recently played/added, filtered by library.

    Sorting logic:
    - For provider playlists (soundcloud, spotify, etc.): Sort by provider_created_at DESC (newest first)
    - For local playlists: Sort by last_played_at DESC, then updated_at DESC

    Args:
        library: Library to filter by. If None, uses active library from database.

    Returns:
        List of playlist dicts with id, name, type, description, track_count, created_at, updated_at, last_played_at
    """
    with get_db_connection() as conn:
        # Get active library if not specified
        if library is None:
            library = sync.get_active_library()

        # Choose sort order based on library type
        if library == "local":
            # Local playlists: Sort by play history
            order_clause = """
                ORDER BY
                    CASE WHEN last_played_at IS NULL THEN 1 ELSE 0 END,
                    last_played_at DESC,
                    updated_at DESC
            """
        else:
            # Provider playlists: Sort by creation date on the provider
            order_clause = """
                ORDER BY
                    CASE WHEN provider_created_at IS NULL THEN 1 ELSE 0 END,
                    provider_created_at DESC
            """

        # Handle 'all' library case - no filtering
        if library == "all":
            where_clause = ""
            params = ()
        else:
            where_clause = "WHERE library = ?"
            params = (library,)

        cursor = conn.execute(
            f"""
            SELECT
                id,
                name,
                type,
                description,
                track_count,
                created_at,
                updated_at,
                last_played_at,
                provider_created_at,
                library
            FROM playlists
            {where_clause}
            {order_clause}
        """,
            params,
        )
        return [dict(row) for row in cursor.fetchall()]


def get_playlist_by_name(
    name: str, library: Optional[str] = None
) -> Optional[dict[str, Any]]:
    """
    Get playlist by name, filtered by library.

    Args:
        name: Playlist name
        library: Library to filter by. If None, uses active library from database.

    Returns:
        Playlist dict or None if not found (includes all columns)
    """
    with get_db_connection() as conn:
        # Get active library if not specified
        if library is None:
            library = sync.get_active_library()

        cursor = conn.execute(
            """
            SELECT * FROM playlists
            WHERE name = ? AND library = ?
        """,
            (name, library),
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def get_playlist_by_id(playlist_id: int) -> Optional[dict[str, Any]]:
    """
    Get playlist by ID.

    Args:
        playlist_id: Playlist ID

    Returns:
        Playlist dict or None if not found (includes all columns including provider IDs)
    """
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            SELECT * FROM playlists WHERE id = ?
        """,
            (playlist_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def get_playlist_tracks(playlist_id: int) -> list[dict[str, Any]]:
    """
    Get all tracks in a playlist.
    For manual playlists, returns tracks in order.
    For smart playlists, evaluates filters and returns matching tracks.

    Args:
        playlist_id: Playlist ID

    Returns:
        List of track dicts with metadata
    """
    playlist = get_playlist_by_id(playlist_id)
    if not playlist:
        return []

    with get_db_connection() as conn:
        if playlist["type"] == "manual":
            # Get tracks from playlist_tracks table in order
            cursor = conn.execute(
                """
                SELECT
                    t.*,
                    pt.position,
                    pt.added_at,
                    COALESCE(per.rating, 1500.0) as playlist_elo_rating,
                    COALESCE(per.comparison_count, 0) as playlist_elo_comparison_count,
                    COALESCE(per.wins, 0) as playlist_elo_wins,
                    COALESCE(er.rating, 1500.0) as global_elo_rating,
                    COALESCE(er.comparison_count, 0) as global_elo_comparison_count,
                    COALESCE(er.wins, 0) as global_elo_wins
                FROM tracks t
                JOIN playlist_tracks pt ON t.id = pt.track_id
                LEFT JOIN playlist_elo_ratings per ON t.id = per.track_id AND per.playlist_id = ?
                LEFT JOIN elo_ratings er ON t.id = er.track_id
                WHERE pt.playlist_id = ?
                ORDER BY pt.position
            """,
                (playlist_id, playlist_id),
            )
            return [dict(row) for row in cursor.fetchall()]
        else:
            # Smart playlist - evaluate filters
            return filters.evaluate_filters(playlist_id)


def get_playlist_track_count(playlist_id: int) -> int:
    """
    Get the number of tracks in a playlist (optimized - doesn't fetch full track data).
    For manual playlists, counts tracks in playlist_tracks table.
    For smart playlists, evaluates filters and counts matching tracks.

    Args:
        playlist_id: Playlist ID

    Returns:
        Number of tracks in playlist
    """
    playlist = get_playlist_by_id(playlist_id)
    if not playlist:
        return 0

    with get_db_connection() as conn:
        if playlist["type"] == "manual":
            # Count tracks directly without fetching data
            cursor = conn.execute(
                """
                SELECT COUNT(*) as count
                FROM playlist_tracks
                WHERE playlist_id = ?
            """,
                (playlist_id,),
            )
            row = cursor.fetchone()
            return row["count"] if row else 0
        else:
            # Smart playlist - need to evaluate filters (no way to optimize without duplicating filter logic)
            tracks = filters.evaluate_filters(playlist_id)
            return len(tracks)


def add_track_to_playlist(playlist_id: int, track_id: int) -> bool:
    """
    Add a track to a manual playlist.

    Args:
        playlist_id: Playlist ID
        track_id: Track ID to add

    Returns:
        True if added successfully, False if already in playlist or playlist not found

    Raises:
        ValueError: If trying to add to a smart playlist
    """
    playlist = get_playlist_by_id(playlist_id)
    if not playlist:
        return False

    if playlist["type"] != "manual":
        raise ValueError("Cannot manually add tracks to smart playlists")

    # Check if track is already in playlist and get soundcloud_id (SoundCloud-first approach)
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            SELECT soundcloud_id FROM tracks
            WHERE id = ? AND NOT EXISTS (
                SELECT 1 FROM playlist_tracks
                WHERE playlist_id = ? AND track_id = ?
            )
        """,
            (track_id, playlist_id, track_id),
        )
        track_row = cursor.fetchone()

        if not track_row:
            return False  # Already in playlist or track doesn't exist

        has_soundcloud_id = track_row["soundcloud_id"] is not None

    # If this needs SoundCloud sync and track is on SoundCloud, sync FIRST
    if sync.should_sync_to_soundcloud(playlist_id) and has_soundcloud_id:
        logger.info(f"Adding track {track_id} to SoundCloud playlist {playlist_id}")
        success, error = sync.add_track_to_soundcloud_playlist(playlist_id, track_id)
        if not success:
            logger.error(f"Failed to add track to SoundCloud: {error}")
            return False
        # Success - sync function already updated database via post-sync
        logger.info(f"Successfully added track {track_id} to SoundCloud and database")
        return True

    # Local-only playlist or local-only track: update database only
    with get_db_connection() as conn:
        # Double-check track is not already in playlist (for local-only path)
        cursor = conn.execute(
            """
            SELECT id FROM playlist_tracks
            WHERE playlist_id = ? AND track_id = ?
        """,
            (playlist_id, track_id),
        )
        if cursor.fetchone():
            return False  # Already in playlist

        # Get next position (0 if playlist is empty, otherwise max + 1)
        cursor = conn.execute(
            """
            SELECT COALESCE(MAX(position) + 1, 0) as next_position
            FROM playlist_tracks
            WHERE playlist_id = ?
        """,
            (playlist_id,),
        )
        next_position = cursor.fetchone()["next_position"]

        # Add track
        conn.execute(
            """
            INSERT INTO playlist_tracks (playlist_id, track_id, position)
            VALUES (?, ?, ?)
        """,
            (playlist_id, track_id, next_position),
        )

        # Update playlist updated_at and track_count
        conn.execute(
            """
            UPDATE playlists
            SET updated_at = CURRENT_TIMESTAMP, track_count = track_count + 1
            WHERE id = ?
        """,
            (playlist_id,),
        )

        conn.commit()
        logger.info(f"Successfully added track {track_id} to local database")

    return True


def remove_track_from_playlist(playlist_id: int, track_id: int) -> bool:
    """
    Remove a track from a manual playlist.

    Args:
        playlist_id: Playlist ID
        track_id: Track ID to remove

    Returns:
        True if removed successfully, False if not in playlist

    Raises:
        ValueError: If trying to remove from a smart playlist
    """
    playlist = get_playlist_by_id(playlist_id)
    if not playlist:
        return False

    if playlist["type"] != "manual":
        raise ValueError("Cannot manually remove tracks from smart playlists")

    logger.info(f"Removing track {track_id} from playlist {playlist_id}")

    # Check if this needs SoundCloud sync (SoundCloud-first approach)
    if sync.should_sync_to_soundcloud(playlist_id):
        # Verify track exists in playlist before attempting SoundCloud sync
        with get_db_connection() as conn:
            cursor = conn.execute(
                """
                SELECT soundcloud_id FROM tracks
                WHERE id = ? AND EXISTS (
                    SELECT 1 FROM playlist_tracks
                    WHERE playlist_id = ? AND track_id = ?
                )
            """,
                (track_id, playlist_id, track_id),
            )
            track_row = cursor.fetchone()

            if not track_row:
                return False  # Track not in playlist

            has_soundcloud_id = track_row["soundcloud_id"] is not None

        # If track is on SoundCloud, sync there FIRST
        if has_soundcloud_id:
            logger.info(
                f"Removing track {track_id} from SoundCloud playlist {playlist_id}"
            )
            success, error = sync.remove_track_from_soundcloud_playlist(
                playlist_id, track_id
            )
            if not success:
                logger.error(f"Failed to remove track from SoundCloud: {error}")
                return False
            # Success - sync function already updated database via post-sync
            logger.info(
                f"Successfully removed track {track_id} from SoundCloud and database"
            )
            return True

    # Local-only playlist or local-only track: update database only
    with get_db_connection() as conn:
        # Begin explicit transaction for atomicity
        conn.execute("BEGIN")
        try:
            # Remove track
            cursor = conn.execute(
                """
                DELETE FROM playlist_tracks
                WHERE playlist_id = ? AND track_id = ?
            """,
                (playlist_id, track_id),
            )

            if cursor.rowcount == 0:
                conn.rollback()
                return False  # Track wasn't in playlist

            # Reorder remaining tracks to fill gap (O(n) instead of O(n²))
            cursor = conn.execute(
                """
                SELECT id FROM playlist_tracks
                WHERE playlist_id = ?
                ORDER BY position
            """,
                (playlist_id,),
            )
            remaining_track_ids = [row["id"] for row in cursor.fetchall()]

            # Update positions in order
            for new_position, playlist_track_id in enumerate(remaining_track_ids):
                conn.execute(
                    """
                    UPDATE playlist_tracks
                    SET position = ?
                    WHERE id = ?
                """,
                    (new_position, playlist_track_id),
                )

            # Update playlist updated_at and track_count
            conn.execute(
                """
                UPDATE playlists
                SET updated_at = CURRENT_TIMESTAMP, track_count = track_count - 1
                WHERE id = ?
            """,
                (playlist_id,),
            )

            conn.commit()
            logger.info(f"Successfully removed track {track_id} from local database")
            return True
        except Exception:
            conn.rollback()
            raise


def reorder_playlist_track(playlist_id: int, from_pos: int, to_pos: int) -> bool:
    """
    Reorder a track within a playlist.

    Args:
        playlist_id: Playlist ID
        from_pos: Current position (0-indexed)
        to_pos: Target position (0-indexed)

    Returns:
        True if reordered successfully, False if positions invalid
    """
    with get_db_connection() as conn:
        # Begin explicit transaction for atomicity
        conn.execute("BEGIN")
        try:
            # Get all tracks in order
            cursor = conn.execute(
                """
                SELECT id, position FROM playlist_tracks
                WHERE playlist_id = ?
                ORDER BY position
            """,
                (playlist_id,),
            )
            tracks = [dict(row) for row in cursor.fetchall()]

            if not tracks or from_pos >= len(tracks) or to_pos >= len(tracks):
                conn.rollback()
                return False

            # Move track from from_pos to to_pos
            track_to_move = tracks.pop(from_pos)
            tracks.insert(to_pos, track_to_move)

            # Update all positions
            for i, track in enumerate(tracks):
                conn.execute(
                    """
                    UPDATE playlist_tracks
                    SET position = ?
                    WHERE id = ?
                """,
                    (i, track["id"]),
                )

            # Update playlist updated_at
            conn.execute(
                """
                UPDATE playlists
                SET updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """,
                (playlist_id,),
            )

            conn.commit()
            return True
        except Exception:
            conn.rollback()
            raise


def set_active_playlist(playlist_id: int) -> bool:
    """
    Set a playlist as the active playlist for the current library.
    Also updates last_played_at timestamp on the playlist.

    Args:
        playlist_id: Playlist ID to activate

    Returns:
        True if set successfully, False if playlist not found
    """
    # Verify playlist exists and get its library
    playlist = get_playlist_by_id(playlist_id)
    if not playlist:
        return False

    library = playlist["library"]

    with get_db_connection() as conn:
        # Update last_played_at on the playlist
        conn.execute(
            """
            UPDATE playlists
            SET last_played_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """,
            (playlist_id,),
        )

        # Insert or update active playlist for this library
        conn.execute(
            """
            INSERT INTO active_playlist (library, playlist_id, activated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(library) DO UPDATE SET
                playlist_id = excluded.playlist_id,
                activated_at = excluded.activated_at
        """,
            (library, playlist_id),
        )
        conn.commit()
        return True


def get_active_playlist(library: Optional[str] = None) -> Optional[dict[str, Any]]:
    """
    Get the currently active playlist for the specified library.

    Args:
        library: Library to get active playlist for. If None, uses active library from database.

    Returns:
        Playlist dict or None if no active playlist
    """
    with get_db_connection() as conn:
        # Get active library if not specified
        if library is None:
            library = sync.get_active_library()

        cursor = conn.execute(
            """
            SELECT p.id, p.name, p.type, p.description, p.created_at, p.updated_at, p.library
            FROM playlists p
            JOIN active_playlist ap ON p.id = ap.playlist_id
            WHERE ap.library = ?
        """,
            (library,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def clear_active_playlist(library: Optional[str] = None) -> bool:
    """
    Clear the active playlist for the current library (return to playing all tracks).

    Args:
        library: Library to clear active playlist for. If None, uses active library from database.

    Returns:
        True if cleared, False if no active playlist was set
    """
    with get_db_connection() as conn:
        # Get active library if not specified
        if library is None:
            library = sync.get_active_library()

        cursor = conn.execute(
            "DELETE FROM active_playlist WHERE library = ?", (library,)
        )
        conn.commit()
        return cursor.rowcount > 0


def get_available_playlist_tracks(playlist_id: int) -> list[str]:
    """
    Get file paths of tracks in a playlist (for playback integration).
    Excludes archived tracks.
    Handles both manual and smart playlists.

    Args:
        playlist_id: Playlist ID

    Returns:
        List of file paths
    """
    playlist = get_playlist_by_id(playlist_id)
    if not playlist:
        return []

    with get_db_connection() as conn:
        if playlist["type"] == "manual":
            # Manual playlist - get from playlist_tracks
            cursor = conn.execute(
                """
                SELECT DISTINCT t.local_path
                FROM tracks t
                JOIN playlist_tracks pt ON t.id = pt.track_id
                LEFT JOIN ratings r ON t.id = r.track_id AND r.rating_type = 'archive'
                WHERE pt.playlist_id = ? AND r.id IS NULL
                ORDER BY pt.position
            """,
                (playlist_id,),
            )
            return [row["local_path"] for row in cursor.fetchall()]
        else:
            # Smart playlist - evaluate filters
            playlist_filters = filters.get_playlist_filters(playlist_id)
            if not playlist_filters:
                return []

            where_clause, params = filters.build_filter_query(playlist_filters)

            # Query with filter and exclude archived tracks
            # Note: f-string is safe here because build_filter_query() validates column names
            # via FIELD_TO_COLUMN whitelist and returns parameterized WHERE clause with ? placeholders
            cursor = conn.execute(
                f"""
                SELECT DISTINCT t.local_path
                FROM tracks t
                LEFT JOIN ratings r ON t.id = r.track_id AND r.rating_type = 'archive'
                WHERE ({where_clause}) AND r.id IS NULL
                ORDER BY t.artist, t.album, t.title
            """,
                params,
            )
            return [row["local_path"] for row in cursor.fetchall()]


# Playlist Builder State Functions


def get_playlist_builder_state(playlist_id: int) -> Optional[dict[str, Any]]:
    """Get saved builder state for a playlist.

    Args:
        playlist_id: Playlist ID

    Returns:
        Dict with scroll_position, sort_field, sort_direction, active_filters (parsed JSON),
        and last_accessed_at, or None if no state exists
    """
    with get_db_connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM playlist_builder_state WHERE playlist_id = ?",
            (playlist_id,),
        )
        row = cursor.fetchone()
        if row:
            result = dict(row)
            # Parse JSON filters
            result["active_filters"] = json.loads(result.get("active_filters", "[]"))
            return result
        return None


def save_playlist_builder_state(
    playlist_id: int,
    scroll_position: int,
    sort_field: str,
    sort_direction: str,
    active_filters: list[dict[str, Any]],
) -> None:
    """Save or update builder state for a playlist (upsert).

    Args:
        playlist_id: Playlist ID
        scroll_position: Current scroll position in the track list
        sort_field: Field to sort by (e.g., 'artist', 'title', 'bpm')
        sort_direction: Sort direction ('asc' or 'desc')
        active_filters: List of active filter dicts
    """
    filters_json = json.dumps(active_filters)
    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO playlist_builder_state
                (playlist_id, scroll_position, sort_field, sort_direction, active_filters, last_accessed_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(playlist_id) DO UPDATE SET
                scroll_position = excluded.scroll_position,
                sort_field = excluded.sort_field,
                sort_direction = excluded.sort_direction,
                active_filters = excluded.active_filters,
                last_accessed_at = CURRENT_TIMESTAMP
        """,
            (playlist_id, scroll_position, sort_field, sort_direction, filters_json),
        )
        conn.commit()


def delete_playlist_builder_state(playlist_id: int) -> bool:
    """Delete builder state for a playlist.

    Note: This is automatically cleaned up when a playlist is deleted due to
    CASCADE constraint. This function is for manual cleanup if needed.

    Args:
        playlist_id: Playlist ID

    Returns:
        True if state was deleted, False if no state existed
    """
    with get_db_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM playlist_builder_state WHERE playlist_id = ?",
            (playlist_id,),
        )
        conn.commit()
        return cursor.rowcount > 0
