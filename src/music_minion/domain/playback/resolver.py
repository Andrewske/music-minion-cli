"""
Playback URI resolution for multi-source tracks.

Handles resolving tracks to playable URIs, with preference for local files
and fallback to streaming services.
"""

from pathlib import Path
from typing import Any, Dict, Optional

from ..library.models import Track


def resolve_playback_uri(
    track: Track, provider_states: Optional[Dict[str, Any]] = None
) -> Optional[str]:
    """Resolve track to playable URI for MPV.

    Preference order:
    1. Local file (best quality, offline)
    2. SoundCloud stream URL
    3. Spotify stream URL
    4. YouTube stream URL

    Args:
        track: Track to resolve
        provider_states: Dictionary of provider states (for auth tokens, etc.)

    Returns:
        Playable URI/path for MPV, or None if track has no available sources

    Examples:
        >>> track = Track(local_path="/home/user/music/song.mp3", soundcloud_id="123")
        >>> resolve_playback_uri(track)
        '/home/user/music/song.mp3'  # Prefers local

        >>> track = Track(local_path="", soundcloud_id="123")
        >>> resolve_playback_uri(track, {'soundcloud': soundcloud_state})
        'https://api.soundcloud.com/tracks/123/stream?oauth_token=...'
    """
    provider_states = provider_states or {}

    # 1. Try local file first (best quality, offline playback)
    if track.local_path and Path(track.local_path).exists():
        return track.local_path

    # 2. Try SoundCloud
    if track.soundcloud_id:
        stream_url = get_soundcloud_stream_url(
            track.soundcloud_id, provider_states.get("soundcloud")
        )
        if stream_url:
            return stream_url

    # 3. Try Spotify
    if track.spotify_id:
        stream_url = get_spotify_stream_url(
            track.spotify_id, provider_states.get("spotify")
        )
        if stream_url:
            return stream_url

    # 4. Try YouTube
    if track.youtube_id:
        # YouTube URLs can be played directly by MPV (via youtube-dl integration)
        return f"https://www.youtube.com/watch?v={track.youtube_id}"

    return None


def get_soundcloud_stream_url(
    track_id: str, provider_state: Optional[Any]
) -> Optional[str]:
    """Get SoundCloud stream URL for a track.

    Args:
        track_id: SoundCloud track ID
        provider_state: SoundCloud provider state (contains auth token)

    Returns:
        Stream URL or None if not authenticated/available
    """
    if not provider_state:
        return None

    # Handle both dict and ProviderState objects
    if hasattr(provider_state, "authenticated"):
        # ProviderState object
        if not provider_state.authenticated:
            return None
        # For ProviderState, get token from cache
        token_data = provider_state.cache.get("token_data", {})
        access_token = token_data.get("access_token")
        if not access_token:
            return None
        return f"https://api.soundcloud.com/tracks/{track_id}/stream?oauth_token={access_token}"
    else:
        # Dictionary format
        if not provider_state.get("authenticated"):
            return None

        # Get OAuth token from provider state
        # Provider state structure: {'authenticated': True, 'token_data': {...}, 'config': {...}}
        token_data = provider_state.get("token_data", {})
        access_token = token_data.get("access_token")

        if not access_token:
            return None

        # Return SoundCloud stream URL
        # MPV will follow redirects to the actual progressive HTTP stream
        return f"https://api.soundcloud.com/tracks/{track_id}/stream?oauth_token={access_token}"


def get_spotify_stream_url(
    track_id: str, provider_state: Optional[Any]
) -> Optional[str]:
    """Get Spotify URI for playback via Spotify Connect API.

    Args:
        track_id: Spotify track ID
        provider_state: Spotify provider state (contains auth token)

    Returns:
        spotify:track:{id} URI for SpotifyPlayer routing, or None if not authenticated

    Note:
        Spotify uses Spotify Connect API for playback, not direct stream URLs.
        Returns a special spotify: URI that will be detected by playback commands
        and routed to SpotifyPlayer instead of MPV.
    """
    if not provider_state:
        return None

    # Handle both dict and ProviderState objects
    if hasattr(provider_state, "authenticated"):
        # ProviderState object
        if not provider_state.authenticated:
            return None
    else:
        # Dictionary format
        if not provider_state.get("authenticated"):
            return None

    # Return Spotify URI for SpotifyPlayer routing
    return f"spotify:track:{track_id}"


def get_youtube_stream_url(
    video_id: str, provider_state: Optional[Any]
) -> Optional[str]:
    """Get YouTube stream URL for a video.

    Args:
        video_id: YouTube video ID
        provider_state: YouTube provider state (not needed for public videos)

    Returns:
        YouTube watch URL (MPV handles youtube-dl integration automatically)

    Note:
        MPV includes youtube-dl support, so we can just return the watch URL.
        MPV will extract the actual stream URL automatically.
    """
    return f"https://www.youtube.com/watch?v={video_id}"


def has_local_source(track: Track) -> bool:
    """Check if track has a local file source."""
    return bool(track.local_path and Path(track.local_path).exists())


def has_streaming_source(track: Track) -> bool:
    """Check if track has any streaming source."""
    return bool(track.soundcloud_id or track.spotify_id or track.youtube_id)


def get_available_sources(track: Track) -> list[str]:
    """Get list of available sources for a track.

    Returns:
        List of source names: ['local', 'soundcloud', 'spotify', 'youtube']
    """
    sources = []

    if track.local_path and Path(track.local_path).exists():
        sources.append("local")

    if track.soundcloud_id:
        sources.append("soundcloud")

    if track.spotify_id:
        sources.append("spotify")

    if track.youtube_id:
        sources.append("youtube")

    return sources
