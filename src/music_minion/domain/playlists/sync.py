"""
Playlist synchronization with streaming providers (SoundCloud, Spotify, etc.).

This module handles bidirectional playlist sync where providers are the source of truth.
Sync strategy:
1. Pull current playlist from provider
2. Update local database to match
3. Add/remove track locally
4. Push updated playlist back to provider
"""

from typing import Optional, Tuple

from loguru import logger

from music_minion.core.database import get_db_connection
from music_minion.domain.library import providers


def get_active_library() -> str:
    """Get the currently active library provider.

    Returns:
        Provider name ('local', 'soundcloud', 'spotify', 'youtube')
        Defaults to 'local' if not set
    """
    with get_db_connection() as conn:
        cursor = conn.execute("SELECT provider FROM active_library WHERE id = 1")
        row = cursor.fetchone()
        return row['provider'] if row else 'local'


def get_provider_state(provider_name: str):
    """Get provider state using standard provider initialization.

    Args:
        provider_name: Name of provider ('soundcloud', 'spotify', etc.)

    Returns:
        Provider state object or None if not authenticated
    """
    from music_minion.domain.library import providers
    from music_minion.domain.library.provider import ProviderConfig

    try:
        provider = providers.get_provider(provider_name)
        config = ProviderConfig(name=provider_name, enabled=True)
        state = provider.init_provider(config)

        # Only return if authenticated
        return state if state.authenticated else None
    except (ValueError, KeyError) as e:
        logger.warning(f"Failed to initialize {provider_name} provider: {e}")
        return None


def should_sync_to_soundcloud(playlist_id: int) -> bool:
    """Check if a playlist should sync to SoundCloud.

    Only syncs when:
    1. Active library is SoundCloud
    2. Playlist has a soundcloud_playlist_id (is linked)

    Args:
        playlist_id: Local playlist ID

    Returns:
        True if should sync to SoundCloud
    """
    # Check if active library is SoundCloud
    active_library = get_active_library()
    if active_library != 'soundcloud':
        return False

    # Check if playlist is linked to SoundCloud
    with get_db_connection() as conn:
        cursor = conn.execute(
            "SELECT soundcloud_playlist_id FROM playlists WHERE id = ?",
            (playlist_id,)
        )
        row = cursor.fetchone()
        return bool(row and row['soundcloud_playlist_id'])


def _ensure_soundcloud_playlist_linked(playlist_id: int, playlist_name: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """Ensure a local playlist is linked to a SoundCloud playlist.

    If playlist doesn't have a soundcloud_playlist_id, creates one on SoundCloud
    and stores the ID in the database.

    Args:
        playlist_id: Local playlist ID
        playlist_name: Playlist name

    Returns:
        (success, soundcloud_playlist_id, error_message)
    """
    # Check if already linked
    with get_db_connection() as conn:
        cursor = conn.execute(
            "SELECT soundcloud_playlist_id FROM playlists WHERE id = ?",
            (playlist_id,)
        )
        row = cursor.fetchone()

        if row and row['soundcloud_playlist_id']:
            return True, row['soundcloud_playlist_id'], None

    # Get SoundCloud provider
    try:
        provider = providers.get_provider('soundcloud')
    except ValueError as e:
        logger.error(f"Failed to get SoundCloud provider: {e}")
        return False, None, str(e)

    # Get provider state
    state = get_provider_state('soundcloud')
    if not state:
        return False, None, "Not authenticated with SoundCloud"

    # Create playlist on SoundCloud
    logger.info(f"Creating SoundCloud playlist for '{playlist_name}'")
    new_state, soundcloud_id, error = provider.create_playlist(
        state,
        name=playlist_name,
        description=f"Synced from Music Minion"
    )

    if not soundcloud_id:
        error_msg = error or "Failed to create SoundCloud playlist"
        logger.error(f"Failed to create SoundCloud playlist '{playlist_name}': {error_msg}")
        return False, None, error_msg

    # Store SoundCloud playlist ID in database
    with get_db_connection() as conn:
        conn.execute(
            """
            UPDATE playlists
            SET soundcloud_playlist_id = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (soundcloud_id, playlist_id)
        )
        conn.commit()

    logger.info(f"Linked playlist '{playlist_name}' to SoundCloud playlist {soundcloud_id}")
    return True, soundcloud_id, None


def sync_playlist_from_soundcloud(playlist_id: int) -> Tuple[bool, Optional[str]]:
    """Pull playlist tracks from SoundCloud and update local database.

    This implements "SoundCloud as source of truth" - overwrites local playlist
    with current SoundCloud state.

    Args:
        playlist_id: Local playlist ID

    Returns:
        (success, error_message)
    """
    # Get playlist info
    with get_db_connection() as conn:
        cursor = conn.execute(
            "SELECT name, soundcloud_playlist_id FROM playlists WHERE id = ?",
            (playlist_id,)
        )
        row = cursor.fetchone()

        if not row:
            return False, "Playlist not found"

        playlist_name = row['name']
        soundcloud_playlist_id = row['soundcloud_playlist_id']

        if not soundcloud_playlist_id:
            return False, f"Playlist '{playlist_name}' not linked to SoundCloud"

    # Get SoundCloud provider
    try:
        provider = providers.get_provider('soundcloud')
    except ValueError as e:
        logger.error(f"Failed to get SoundCloud provider for sync: {e}")
        return False, str(e)

    # Get provider state
    state = get_provider_state('soundcloud')
    if not state:
        logger.error("Not authenticated with SoundCloud for playlist sync")
        return False, "Not authenticated with SoundCloud"

    # Fetch playlist tracks from SoundCloud
    logger.debug(f"Fetching tracks for SoundCloud playlist {soundcloud_playlist_id}")
    new_state, tracks = provider.get_playlist_tracks(state, soundcloud_playlist_id)

    # Check for authentication failure
    if not new_state.authenticated:
        logger.error("Lost authentication while fetching playlist tracks from SoundCloud")
        return False, "Authentication failed while fetching playlist"

    # Empty tracks list could mean empty playlist or error (errors handled internally by provider)
    if not tracks:
        logger.warning(f"No tracks found in SoundCloud playlist {soundcloud_playlist_id} (could be empty or error)")

    # Update local database to match SoundCloud
    # Strategy: Clear local playlist and re-add all tracks in order
    with get_db_connection() as conn:
        # Begin transaction
        conn.execute("BEGIN")
        try:
            # Clear existing tracks
            conn.execute(
                "DELETE FROM playlist_tracks WHERE playlist_id = ?",
                (playlist_id,)
            )

            # Add tracks in order
            # tracks is a list of tuples: [(track_id, metadata), ...]
            for position, track_data in enumerate(tracks):
                soundcloud_id, metadata = track_data  # Unpack tuple

                # Find local track by soundcloud_id
                cursor = conn.execute(
                    "SELECT id FROM tracks WHERE soundcloud_id = ?",
                    (soundcloud_id,)
                )
                track_row = cursor.fetchone()

                if track_row:
                    track_id = track_row['id']
                    conn.execute(
                        """
                        INSERT INTO playlist_tracks (playlist_id, track_id, position)
                        VALUES (?, ?, ?)
                        """,
                        (playlist_id, track_id, position)
                    )
                else:
                    logger.warning(
                        f"Track {soundcloud_id} in SoundCloud playlist not found in local database"
                    )

            # Update playlist metadata
            conn.execute(
                """
                UPDATE playlists
                SET track_count = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (len([t for t in tracks if t]), playlist_id)  # Count non-null tracks
            )

            conn.commit()
            logger.info(f"Synced {len(tracks)} tracks from SoundCloud for playlist '{playlist_name}'")
            return True, None

        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to sync playlist from SoundCloud: {str(e)}", exc_info=True)
            return False, f"Database error: {str(e)}"


def add_track_to_soundcloud_playlist(playlist_id: int, track_id: int) -> Tuple[bool, Optional[str]]:
    """Add a track to a SoundCloud playlist with full sync flow.

    Strategy (SoundCloud as source of truth):
    1. Pull current playlist from SoundCloud
    2. Update local database to match
    3. Get track's soundcloud_id
    4. Add track to playlist on SoundCloud
    5. Update local database with final state

    Args:
        playlist_id: Local playlist ID
        track_id: Local track ID

    Returns:
        (success, error_message)
    """
    # Get playlist and track info
    with get_db_connection() as conn:
        # Get playlist
        cursor = conn.execute(
            "SELECT name, soundcloud_playlist_id FROM playlists WHERE id = ?",
            (playlist_id,)
        )
        playlist_row = cursor.fetchone()

        if not playlist_row:
            return False, "Playlist not found"

        playlist_name = playlist_row['name']
        soundcloud_playlist_id = playlist_row['soundcloud_playlist_id']

        # Get track
        cursor = conn.execute(
            "SELECT soundcloud_id FROM tracks WHERE id = ?",
            (track_id,)
        )
        track_row = cursor.fetchone()

        if not track_row:
            return False, "Track not found"

        soundcloud_track_id = track_row['soundcloud_id']

        if not soundcloud_track_id:
            logger.warning(f"Track {track_id} has no soundcloud_id, skipping sync")
            return True, None  # Success but no sync (local-only track)

    # Ensure playlist is linked to SoundCloud
    if not soundcloud_playlist_id:
        success, soundcloud_playlist_id, error = _ensure_soundcloud_playlist_linked(
            playlist_id, playlist_name
        )
        if not success:
            return False, error

    # Step 1: Sync from SoundCloud first (get current state)
    sync_success, sync_error = sync_playlist_from_soundcloud(playlist_id)
    if not sync_success:
        return False, f"Failed to sync before adding track: {sync_error}"

    # Step 2: Add track to SoundCloud playlist
    try:
        provider = providers.get_provider('soundcloud')
    except ValueError as e:
        logger.error(f"Failed to get SoundCloud provider: {e}")
        return False, str(e)

    state = get_provider_state('soundcloud')
    if not state:
        logger.error("Not authenticated with SoundCloud")
        return False, "Not authenticated with SoundCloud"

    logger.info(f"Adding track {soundcloud_track_id} to SoundCloud playlist {soundcloud_playlist_id}")
    new_state, success, error = provider.add_track_to_playlist(
        state,
        soundcloud_playlist_id,
        soundcloud_track_id
    )

    if not success:
        error_msg = error or "Failed to add track to SoundCloud playlist"
        logger.error(f"Failed to add track to SoundCloud: {error_msg}")
        return False, error_msg

    # Step 3: Sync from SoundCloud again (get final state)
    sync_success, sync_error = sync_playlist_from_soundcloud(playlist_id)
    if not sync_success:
        logger.warning(f"Track added to SoundCloud but local sync failed: {sync_error}")
        # Don't return error - track was added successfully to SoundCloud

    logger.info(f"Successfully added track to SoundCloud playlist '{playlist_name}'")
    return True, None


def remove_track_from_soundcloud_playlist(playlist_id: int, track_id: int) -> Tuple[bool, Optional[str]]:
    """Remove a track from a SoundCloud playlist with full sync flow.

    Strategy (SoundCloud as source of truth):
    1. Pull current playlist from SoundCloud
    2. Update local database to match
    3. Get track's soundcloud_id
    4. Remove track from playlist on SoundCloud
    5. Update local database with final state

    Args:
        playlist_id: Local playlist ID
        track_id: Local track ID

    Returns:
        (success, error_message)
    """
    # Get playlist and track info
    with get_db_connection() as conn:
        # Get playlist
        cursor = conn.execute(
            "SELECT name, soundcloud_playlist_id FROM playlists WHERE id = ?",
            (playlist_id,)
        )
        playlist_row = cursor.fetchone()

        if not playlist_row:
            return False, "Playlist not found"

        playlist_name = playlist_row['name']
        soundcloud_playlist_id = playlist_row['soundcloud_playlist_id']

        if not soundcloud_playlist_id:
            logger.warning(f"Playlist '{playlist_name}' not linked to SoundCloud, skipping sync")
            return True, None  # Success but no sync (local-only playlist)

        # Get track
        cursor = conn.execute(
            "SELECT soundcloud_id FROM tracks WHERE id = ?",
            (track_id,)
        )
        track_row = cursor.fetchone()

        if not track_row:
            return False, "Track not found"

        soundcloud_track_id = track_row['soundcloud_id']

        if not soundcloud_track_id:
            logger.warning(f"Track {track_id} has no soundcloud_id, skipping sync")
            return True, None  # Success but no sync (local-only track)

    # Step 1: Sync from SoundCloud first (get current state)
    sync_success, sync_error = sync_playlist_from_soundcloud(playlist_id)
    if not sync_success:
        return False, f"Failed to sync before removing track: {sync_error}"

    # Step 2: Remove track from SoundCloud playlist
    try:
        provider = providers.get_provider('soundcloud')
    except ValueError as e:
        logger.error(f"Failed to get SoundCloud provider: {e}")
        return False, str(e)

    state = get_provider_state('soundcloud')
    if not state:
        logger.error("Not authenticated with SoundCloud")
        return False, "Not authenticated with SoundCloud"

    logger.info(f"Removing track {soundcloud_track_id} from SoundCloud playlist {soundcloud_playlist_id}")
    new_state, success, error = provider.remove_track_from_playlist(
        state,
        soundcloud_playlist_id,
        soundcloud_track_id
    )

    if not success:
        error_msg = error or "Failed to remove track from SoundCloud playlist"
        logger.error(f"Failed to remove track from SoundCloud: {error_msg}")
        return False, error_msg

    # Step 3: Sync from SoundCloud again (get final state)
    sync_success, sync_error = sync_playlist_from_soundcloud(playlist_id)
    if not sync_success:
        logger.warning(f"Track removed from SoundCloud but local sync failed: {sync_error}")
        # Don't return error - track was removed successfully from SoundCloud

    logger.info(f"Successfully removed track from SoundCloud playlist '{playlist_name}'")
    return True, None
