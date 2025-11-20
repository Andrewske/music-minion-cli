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
    """Initialize SoundCloud provider.

    Tries to load state from database first, then falls back to file tokens.

    Args:
        config: Provider configuration

    Returns:
        Initial provider state
    """
    from music_minion.core import database

    # Try to load state from database
    db_state = database.load_provider_state("soundcloud")

    if db_state and db_state.get("authenticated"):
        # Load cached auth data
        auth_data = db_state["auth_data"]

        # Check if token expired
        if auth.is_token_expired(auth_data):
            # Try to refresh the token
            refreshed_token = auth.refresh_token(auth_data)
            if refreshed_token:
                # Update database with refreshed token
                database.save_provider_state("soundcloud", refreshed_token, db_state.get("config", {}))
                return ProviderState(
                    config=config,
                    authenticated=True,
                    last_sync=None,
                    cache={"token_data": refreshed_token},
                )
            # Refresh failed, fall through to check file tokens
        else:
            # Token still valid
            return ProviderState(
                config=config,
                authenticated=True,
                last_sync=None,
                cache={"token_data": auth_data},
            )

    # Fall back to file-based tokens (for backward compatibility)
    token_data = auth._load_user_tokens()

    if token_data:
        if auth.is_token_expired(token_data):
            # Try to refresh the file-based token
            refreshed_token = auth.refresh_token(token_data)
            if refreshed_token:
                # Save to database for future use
                database.save_provider_state("soundcloud", refreshed_token, {})
                return ProviderState(
                    config=config,
                    authenticated=True,
                    last_sync=None,
                    cache={"token_data": refreshed_token},
                )
            # Refresh failed, fall through to unauthenticated
        else:
            # Token still valid
            return ProviderState(
                config=config,
                authenticated=True,
                last_sync=None,
                cache={"token_data": token_data},
            )

    # Not authenticated or token expired
    return ProviderState(config=config, authenticated=False, last_sync=None, cache={})


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
