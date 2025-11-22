"""
Spotify provider for Music Minion.

Implements OAuth 2.0 + PKCE authentication and API access for Spotify.
"""

from typing import Tuple

from loguru import logger

from music_minion.core.output import log
from ...provider import ProviderConfig, ProviderState, TrackList

# Import from submodules
from . import api, auth


def init_provider(config: ProviderConfig) -> ProviderState:
    """Initialize Spotify provider with token lookup and auto-refresh.

    NOTE: This function performs more work than typical __init__.py exports
    because it needs to load authentication state from multiple sources
    with automatic token refresh.

    Token Lookup Priority:
    1. Database provider_state table (primary, persisted)
       - Includes auto-refresh if token expired
    2. File-based tokens (legacy, ~/.local/share/music-minion/spotify/)
       - Auto-migrates to database on successful refresh
    3. Unauthenticated state (requires 'library auth spotify')

    This complexity is justified because:
    - Avoids forcing all callers to handle token refresh
    - Provides seamless migration from file-based to DB storage
    - Follows provider protocol (returns ProviderState)
    - Initialization happens once per session, not per-operation

    Args:
        config: Provider configuration

    Returns:
        ProviderState with authentication status and cached token data
    """
    from music_minion.core import database

    logger.debug("Initializing Spotify provider")

    # Inject config into cache for auth functions to access
    config_dict = {
        "client_id": config.client_id if hasattr(config, 'client_id') else "",
        "client_secret": config.client_secret if hasattr(config, 'client_secret') else "",
        "redirect_uri": getattr(config, 'redirect_uri', "http://localhost:8080/callback"),
    }

    # Try to load state from database
    db_state = database.load_provider_state("spotify")

    if db_state and db_state.get("authenticated"):
        # Load cached auth data
        auth_data = db_state["auth_data"]
        logger.debug("Found Spotify tokens in database")

        # Check if token expired
        if auth.is_token_expired(auth_data):
            logger.info("Spotify token expired, attempting refresh")
            # Try to refresh the token
            refreshed_token = auth.refresh_token(auth_data)
            if refreshed_token:
                # Update database with refreshed token
                database.save_provider_state("spotify", refreshed_token, db_state.get("config", {}))
                logger.info("Spotify token refreshed successfully")
                return ProviderState(
                    config=config,
                    authenticated=True,
                    last_sync=None,
                    cache={"token_data": refreshed_token, "config": config_dict},
                )
            logger.warning("Spotify token refresh failed")
            log("⚠ Spotify authentication expired. Run: library auth spotify", level="warning")
            # Refresh failed, return unauthenticated state
            return ProviderState(
                config=config,
                authenticated=False,
                last_sync=None,
                cache={"config": config_dict}
            )
        else:
            # Token still valid
            logger.debug("Spotify token is valid")
            return ProviderState(
                config=config,
                authenticated=True,
                last_sync=None,
                cache={"token_data": auth_data, "config": config_dict},
            )

    # Fall back to file-based tokens (for backward compatibility)
    logger.debug("Checking for file-based Spotify tokens")
    token_data = auth._load_user_tokens()

    if token_data:
        logger.info("Found file-based Spotify tokens")
        if auth.is_token_expired(token_data):
            logger.info("File-based token expired, attempting refresh")
            # Try to refresh the file-based token
            refreshed_token = auth.refresh_token(token_data)
            if refreshed_token:
                # Save to database for future use (migration)
                database.save_provider_state("spotify", refreshed_token, {})
                logger.info("Migrated file-based tokens to database")
                return ProviderState(
                    config=config,
                    authenticated=True,
                    last_sync=None,
                    cache={"token_data": refreshed_token, "config": config_dict},
                )
            logger.warning("File-based token refresh failed")
            log("⚠ Spotify authentication expired. Run: library auth spotify", level="warning")
            # Refresh failed, return unauthenticated state
            return ProviderState(
                config=config,
                authenticated=False,
                last_sync=None,
                cache={"config": config_dict}
            )
        else:
            # Token still valid
            logger.debug("File-based token is valid")
            return ProviderState(
                config=config,
                authenticated=True,
                last_sync=None,
                cache={"token_data": token_data, "config": config_dict},
            )

    # Not authenticated or token expired
    logger.debug("Spotify provider not authenticated")
    return ProviderState(
        config=config,
        authenticated=False,
        last_sync=None,
        cache={"config": config_dict}
    )


# Re-export authentication functions
authenticate = auth.authenticate

# Re-export API functions
sync_library = api.sync_library
search = api.search
get_stream_url = api.get_stream_url
get_playlists = api.get_playlists
get_playlist_tracks = api.get_playlist_tracks
like_track = api.like_track
unlike_track = api.unlike_track
add_track_to_playlist = api.add_track_to_playlist
remove_track_from_playlist = api.remove_track_from_playlist
create_playlist = api.create_playlist


__all__ = [
    "init_provider",
    "authenticate",
    "sync_library",
    "search",
    "get_stream_url",
    "get_playlists",
    "get_playlist_tracks",
    "like_track",
    "unlike_track",
    "add_track_to_playlist",
    "remove_track_from_playlist",
    "create_playlist",
]
