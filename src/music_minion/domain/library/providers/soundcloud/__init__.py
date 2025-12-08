"""
SoundCloud provider for Music Minion.

Implements OAuth 2.0 authentication and API access for SoundCloud.
Adapted from soundcloud-discovery project.
"""

from typing import Tuple

from ...provider import ProviderConfig, ProviderState, TrackList

# Import from submodules
from . import api, auth


def init_provider(config: ProviderConfig) -> ProviderState:
    """Initialize SoundCloud provider with file-based token management.

    Token Loading:
    1. Load from file (~/.local/share/music-minion/soundcloud/user_tokens.json)
    2. If token exists and not expired, use it
    3. If token expired, attempt refresh
    4. If refresh fails, return unauthenticated (user must re-auth)

    Args:
        config: Provider configuration

    Returns:
        ProviderState with authentication status and cached token data
    """
    from loguru import logger

    # Load token from file
    token_data = auth._load_user_tokens()

    if not token_data:
        logger.debug("No SoundCloud token found - not authenticated")
        return ProviderState(
            config=config, authenticated=False, last_sync=None, cache={}
        )

    # Check if token is expired
    if auth.is_token_expired(token_data):
        logger.info("SoundCloud token expired, attempting refresh")
        refreshed_token = auth.refresh_token(token_data)

        if refreshed_token:
            logger.info("Successfully refreshed SoundCloud token")
            return ProviderState(
                config=config,
                authenticated=True,
                last_sync=None,
                cache={"token_data": refreshed_token},
            )
        else:
            logger.warning(
                "Token refresh failed - please re-authenticate with: library auth soundcloud"
            )
            return ProviderState(
                config=config, authenticated=False, last_sync=None, cache={}
            )

    # Token is still valid
    logger.debug("SoundCloud token is valid")
    return ProviderState(
        config=config,
        authenticated=True,
        last_sync=None,
        cache={"token_data": token_data},
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
