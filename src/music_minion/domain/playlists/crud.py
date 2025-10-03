"""
Playlist management for Music Minion CLI
Functional approach with explicit state passing
"""

from typing import List, Optional, Dict, Any
from datetime import datetime

from music_minion.core.database import get_db_connection
from . import filters


def create_playlist(name: str, playlist_type: str, description: Optional[str] = None) -> int:
    """
    Create a new playlist.

    Args:
        name: Playlist name (must be unique)
        playlist_type: 'manual' or 'smart'
        description: Optional description

    Returns:
        Playlist ID

    Raises:
        ValueError: If playlist name already exists or type is invalid
    """
    if playlist_type not in ['manual', 'smart']:
        raise ValueError(f"Invalid playlist type: {playlist_type}. Must be 'manual' or 'smart'")

    with get_db_connection() as conn:
        try:
            cursor = conn.execute("""
                INSERT INTO playlists (name, type, description)
                VALUES (?, ?, ?)
            """, (name, playlist_type, description))
            conn.commit()
            return cursor.lastrowid
        except Exception as e:
            if 'UNIQUE constraint failed' in str(e):
                raise ValueError(f"Playlist '{name}' already exists")
            raise


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
            if playlist['type'] == 'manual':
                # Count tracks in playlist_tracks table
                cursor = conn.execute("""
                    SELECT COUNT(*) as count
                    FROM playlist_tracks
                    WHERE playlist_id = ?
                """, (playlist_id,))
                count = cursor.fetchone()['count']
            else:
                # Smart playlist - evaluate filters
                matching_tracks = filters.evaluate_filters(playlist_id)
                count = len(matching_tracks)

            conn.execute("""
                UPDATE playlists
                SET track_count = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (count, playlist_id))
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
            # Clear active playlist if this is the active one
            cursor = conn.execute("SELECT playlist_id FROM active_playlist WHERE id = 1")
            row = cursor.fetchone()
            if row and row['playlist_id'] == playlist_id:
                conn.execute("DELETE FROM active_playlist WHERE id = 1")

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
            cursor = conn.execute("""
                UPDATE playlists
                SET name = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (new_name, playlist_id))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            if 'UNIQUE constraint failed' in str(e):
                raise ValueError(f"Playlist '{new_name}' already exists")
            raise


def get_all_playlists() -> List[Dict[str, Any]]:
    """
    Get all playlists with metadata.

    Returns:
        List of playlist dicts with id, name, type, description, created_at, updated_at, track_count
    """
    with get_db_connection() as conn:
        cursor = conn.execute("""
            SELECT
                id,
                name,
                type,
                description,
                track_count,
                created_at,
                updated_at,
                last_played_at
            FROM playlists
            ORDER BY name
        """)
        return [dict(row) for row in cursor.fetchall()]


def get_playlists_sorted_by_recent() -> List[Dict[str, Any]]:
    """
    Get all playlists sorted by recently played/added.
    Playlists with last_played_at come first (most recent first),
    then playlists by updated_at (most recent first).

    Returns:
        List of playlist dicts with id, name, type, description, track_count, created_at, updated_at, last_played_at
    """
    with get_db_connection() as conn:
        cursor = conn.execute("""
            SELECT
                id,
                name,
                type,
                description,
                track_count,
                created_at,
                updated_at,
                last_played_at
            FROM playlists
            ORDER BY
                CASE WHEN last_played_at IS NULL THEN 1 ELSE 0 END,
                last_played_at DESC,
                updated_at DESC
        """)
        return [dict(row) for row in cursor.fetchall()]


def get_playlist_by_name(name: str) -> Optional[Dict[str, Any]]:
    """
    Get playlist by name.

    Args:
        name: Playlist name

    Returns:
        Playlist dict or None if not found
    """
    with get_db_connection() as conn:
        cursor = conn.execute("""
            SELECT id, name, type, description, created_at, updated_at
            FROM playlists
            WHERE name = ?
        """, (name,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_playlist_by_id(playlist_id: int) -> Optional[Dict[str, Any]]:
    """
    Get playlist by ID.

    Args:
        playlist_id: Playlist ID

    Returns:
        Playlist dict or None if not found
    """
    with get_db_connection() as conn:
        cursor = conn.execute("""
            SELECT id, name, type, description, created_at, updated_at
            FROM playlists
            WHERE id = ?
        """, (playlist_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_playlist_tracks(playlist_id: int) -> List[Dict[str, Any]]:
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
        if playlist['type'] == 'manual':
            # Get tracks from playlist_tracks table in order
            cursor = conn.execute("""
                SELECT
                    t.*,
                    pt.position,
                    pt.added_at
                FROM tracks t
                JOIN playlist_tracks pt ON t.id = pt.track_id
                WHERE pt.playlist_id = ?
                ORDER BY pt.position
            """, (playlist_id,))
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
        if playlist['type'] == 'manual':
            # Count tracks directly without fetching data
            cursor = conn.execute("""
                SELECT COUNT(*) as count
                FROM playlist_tracks
                WHERE playlist_id = ?
            """, (playlist_id,))
            row = cursor.fetchone()
            return row['count'] if row else 0
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

    if playlist['type'] != 'manual':
        raise ValueError("Cannot manually add tracks to smart playlists")

    with get_db_connection() as conn:
        # Check if track is already in playlist
        cursor = conn.execute("""
            SELECT id FROM playlist_tracks
            WHERE playlist_id = ? AND track_id = ?
        """, (playlist_id, track_id))
        if cursor.fetchone():
            return False  # Already in playlist

        # Get next position (0 if playlist is empty, otherwise max + 1)
        cursor = conn.execute("""
            SELECT COALESCE(MAX(position) + 1, 0) as next_position
            FROM playlist_tracks
            WHERE playlist_id = ?
        """, (playlist_id,))
        next_position = cursor.fetchone()['next_position']

        # Add track
        conn.execute("""
            INSERT INTO playlist_tracks (playlist_id, track_id, position)
            VALUES (?, ?, ?)
        """, (playlist_id, track_id, next_position))

        # Update playlist updated_at and track_count
        conn.execute("""
            UPDATE playlists
            SET updated_at = CURRENT_TIMESTAMP, track_count = track_count + 1
            WHERE id = ?
        """, (playlist_id,))

        conn.commit()
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

    if playlist['type'] != 'manual':
        raise ValueError("Cannot manually remove tracks from smart playlists")

    with get_db_connection() as conn:
        # Begin explicit transaction for atomicity
        conn.execute("BEGIN")
        try:
            # Remove track
            cursor = conn.execute("""
                DELETE FROM playlist_tracks
                WHERE playlist_id = ? AND track_id = ?
            """, (playlist_id, track_id))

            if cursor.rowcount == 0:
                conn.rollback()
                return False  # Track wasn't in playlist

            # Reorder remaining tracks to fill gap (O(n) instead of O(n²))
            cursor = conn.execute("""
                SELECT id FROM playlist_tracks
                WHERE playlist_id = ?
                ORDER BY position
            """, (playlist_id,))
            remaining_track_ids = [row['id'] for row in cursor.fetchall()]

            # Update positions in order
            for new_position, track_id in enumerate(remaining_track_ids):
                conn.execute("""
                    UPDATE playlist_tracks
                    SET position = ?
                    WHERE id = ?
                """, (new_position, track_id))

            # Update playlist updated_at and track_count
            conn.execute("""
                UPDATE playlists
                SET updated_at = CURRENT_TIMESTAMP, track_count = track_count - 1
                WHERE id = ?
            """, (playlist_id,))

            conn.commit()
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
            cursor = conn.execute("""
                SELECT id, position FROM playlist_tracks
                WHERE playlist_id = ?
                ORDER BY position
            """, (playlist_id,))
            tracks = [dict(row) for row in cursor.fetchall()]

            if not tracks or from_pos >= len(tracks) or to_pos >= len(tracks):
                conn.rollback()
                return False

            # Move track from from_pos to to_pos
            track_to_move = tracks.pop(from_pos)
            tracks.insert(to_pos, track_to_move)

            # Update all positions
            for i, track in enumerate(tracks):
                conn.execute("""
                    UPDATE playlist_tracks
                    SET position = ?
                    WHERE id = ?
                """, (i, track['id']))

            # Update playlist updated_at
            conn.execute("""
                UPDATE playlists
                SET updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (playlist_id,))

            conn.commit()
            return True
        except Exception:
            conn.rollback()
            raise


def set_active_playlist(playlist_id: int) -> bool:
    """
    Set a playlist as the active playlist for playback filtering.
    Also updates last_played_at timestamp on the playlist.

    Args:
        playlist_id: Playlist ID to activate

    Returns:
        True if set successfully, False if playlist not found
    """
    # Verify playlist exists
    if not get_playlist_by_id(playlist_id):
        return False

    with get_db_connection() as conn:
        # Update last_played_at on the playlist
        conn.execute("""
            UPDATE playlists
            SET last_played_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (playlist_id,))

        # Insert or update active playlist (only one row allowed)
        conn.execute("""
            INSERT INTO active_playlist (id, playlist_id, activated_at)
            VALUES (1, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET
                playlist_id = excluded.playlist_id,
                activated_at = excluded.activated_at
        """, (playlist_id,))
        conn.commit()
        return True


def get_active_playlist() -> Optional[Dict[str, Any]]:
    """
    Get the currently active playlist.

    Returns:
        Playlist dict or None if no active playlist
    """
    with get_db_connection() as conn:
        cursor = conn.execute("""
            SELECT p.id, p.name, p.type, p.description, p.created_at, p.updated_at
            FROM playlists p
            JOIN active_playlist ap ON p.id = ap.playlist_id
            WHERE ap.id = 1
        """)
        row = cursor.fetchone()
        return dict(row) if row else None


def clear_active_playlist() -> bool:
    """
    Clear the active playlist (return to playing all tracks).

    Returns:
        True if cleared, False if no active playlist was set
    """
    with get_db_connection() as conn:
        cursor = conn.execute("DELETE FROM active_playlist WHERE id = 1")
        conn.commit()
        return cursor.rowcount > 0


def get_available_playlist_tracks(playlist_id: int) -> List[str]:
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
        if playlist['type'] == 'manual':
            # Manual playlist - get from playlist_tracks
            cursor = conn.execute("""
                SELECT DISTINCT t.file_path
                FROM tracks t
                JOIN playlist_tracks pt ON t.id = pt.track_id
                LEFT JOIN ratings r ON t.id = r.track_id AND r.rating_type = 'archive'
                WHERE pt.playlist_id = ? AND r.id IS NULL
                ORDER BY pt.position
            """, (playlist_id,))
            return [row['file_path'] for row in cursor.fetchall()]
        else:
            # Smart playlist - evaluate filters
            playlist_filters = filters.get_playlist_filters(playlist_id)
            if not playlist_filters:
                return []

            where_clause, params = filters.build_filter_query(playlist_filters)

            # Query with filter and exclude archived tracks
            # Note: f-string is safe here because build_filter_query() validates column names
            # via FIELD_TO_COLUMN whitelist and returns parameterized WHERE clause with ? placeholders
            cursor = conn.execute(f"""
                SELECT DISTINCT t.file_path
                FROM tracks t
                LEFT JOIN ratings r ON t.id = r.track_id AND r.rating_type = 'archive'
                WHERE ({where_clause}) AND r.id IS NULL
                ORDER BY t.artist, t.album, t.title
            """, params)
            return [row['file_path'] for row in cursor.fetchall()]