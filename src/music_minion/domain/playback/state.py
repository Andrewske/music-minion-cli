"""
Playback state management for Music Minion CLI

Handles shuffle mode and playlist position tracking for enhanced playback control.
"""

from typing import Optional, Tuple, Dict, Any
from music_minion.core.database import get_db_connection


def get_shuffle_mode() -> bool:
    """
    Get current shuffle mode setting.

    Returns:
        True if shuffle is enabled, False for sequential playback
    """
    with get_db_connection() as conn:
        cursor = conn.execute("""
            SELECT shuffle_enabled FROM playback_state WHERE id = 1
        """)
        row = cursor.fetchone()
        # Default to True (shuffle) if not set
        return row['shuffle_enabled'] if row else True


def set_shuffle_mode(enabled: bool) -> None:
    """
    Set shuffle mode (global setting).

    Args:
        enabled: True for shuffle mode, False for sequential playback
    """
    with get_db_connection() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO playback_state (id, shuffle_enabled, updated_at)
            VALUES (1, ?, CURRENT_TIMESTAMP)
        """, (enabled,))
        conn.commit()


def update_playlist_position(playlist_id: int, track_id: int, position: int) -> None:
    """
    Update the last played position in a playlist.

    Args:
        playlist_id: ID of the active playlist
        track_id: ID of the track being played
        position: Index position in the playlist (0-based)
    """
    with get_db_connection() as conn:
        conn.execute("""
            UPDATE active_playlist
            SET last_played_track_id = ?,
                last_played_position = ?,
                last_played_at = CURRENT_TIMESTAMP
            WHERE playlist_id = ?
        """, (track_id, position, playlist_id))
        conn.commit()


def get_playlist_position(playlist_id: int) -> Optional[Tuple[int, int]]:
    """
    Get the last played position in a playlist.

    Args:
        playlist_id: ID of the playlist

    Returns:
        Tuple of (track_id, position) if available, None otherwise
    """
    with get_db_connection() as conn:
        cursor = conn.execute("""
            SELECT last_played_track_id, last_played_position
            FROM active_playlist
            WHERE playlist_id = ?
        """, (playlist_id,))
        row = cursor.fetchone()

        if row and row['last_played_track_id'] is not None:
            return (row['last_played_track_id'], row['last_played_position'])
        return None


def clear_playlist_position(playlist_id: int) -> None:
    """
    Clear the saved position for a playlist (reset to beginning).

    Args:
        playlist_id: ID of the playlist
    """
    with get_db_connection() as conn:
        conn.execute("""
            UPDATE active_playlist
            SET last_played_track_id = NULL,
                last_played_position = NULL,
                last_played_at = NULL
            WHERE playlist_id = ?
        """, (playlist_id,))
        conn.commit()


def get_next_sequential_track(tracks: list[Dict[str, Any]],
                              current_track_id: Optional[int]) -> Optional[Dict[str, Any]]:
    """
    Get the next track in sequential order from a list of tracks.

    Args:
        tracks: List of track dictionaries (from get_playlist_tracks)
        current_track_id: ID of the current track, or None to start from beginning

    Returns:
        Next track dictionary, or None if track list is empty or current track not found
        Note: When current_track_id is None, returns first track (start from beginning)
    """
    if not tracks:
        return None

    # If no current track, return first track
    if current_track_id is None:
        return tracks[0]

    # Find current track and return next one
    for i, track in enumerate(tracks):
        if track['id'] == current_track_id:
            # Return next track if not at end
            if i + 1 < len(tracks):
                return tracks[i + 1]
            # At end, loop back to beginning
            return tracks[0]

    # Current track not found in playlist - return None to signal error
    return None


def get_track_position_in_playlist(tracks: list[Dict[str, Any]],
                                   track_id: int) -> Optional[int]:
    """
    Get the position (0-based index) of a track in a playlist.

    IMPORTANT: Position is 0-indexed internally (0, 1, 2, ...) but displayed
    as 1-indexed to users (1, 2, 3, ...). Always add 1 when showing to users.

    Args:
        tracks: List of track dictionaries (from get_playlist_tracks)
        track_id: ID of the track to find

    Returns:
        0-based position of track, or None if not found
    """
    for i, track in enumerate(tracks):
        if track['id'] == track_id:
            return i
    return None
