"""
Provider interface for music library sources.

Defines the protocol for implementing music library providers (local files,
SoundCloud, Spotify, YouTube, etc.) using a functional programming approach.

Providers are implemented as modules with pure functions, not classes.
This protocol just defines the contract that provider modules must follow.
"""

from typing import Protocol, List, Tuple, Dict, Any, Optional
from dataclasses import dataclass, field
import time


@dataclass
class ProviderConfig:
    """Base configuration for a provider."""
    name: str  # Provider name: "local", "soundcloud", "spotify", etc.
    enabled: bool = True
    cache_duration_hours: int = 24  # How long to cache synced data


@dataclass
class ProviderState:
    """Runtime state for a provider.

    Immutable state container passed to all provider functions.
    Functions return new ProviderState instead of mutating.
    """
    config: ProviderConfig
    authenticated: bool = False
    last_sync: Optional[float] = None  # Unix timestamp
    cache: Dict[str, Any] = field(default_factory=dict)  # In-memory cache

    def with_authenticated(self, authenticated: bool) -> 'ProviderState':
        """Return new state with updated authentication status."""
        return ProviderState(
            config=self.config,
            authenticated=authenticated,
            last_sync=self.last_sync,
            cache=self.cache
        )

    def with_cache(self, **updates) -> 'ProviderState':
        """Return new state with updated cache entries."""
        new_cache = {**self.cache, **updates}
        return ProviderState(
            config=self.config,
            authenticated=self.authenticated,
            last_sync=self.last_sync,
            cache=new_cache
        )

    def with_sync_time(self, timestamp: Optional[float] = None) -> 'ProviderState':
        """Return new state with updated sync timestamp."""
        return ProviderState(
            config=self.config,
            authenticated=self.authenticated,
            last_sync=timestamp or time.time(),
            cache=self.cache
        )

    def needs_sync(self) -> bool:
        """Check if cache has expired and needs refresh."""
        if self.last_sync is None:
            return True

        age_hours = (time.time() - self.last_sync) / 3600
        return age_hours >= self.config.cache_duration_hours


class LibraryProvider(Protocol):
    """Protocol defining the interface for music library providers.

    Providers are implemented as modules with pure functions following this contract.
    All functions take ProviderState and return (new_state, result) tuples.

    Example provider module structure:

        # domain/library/providers/soundcloud.py

        def init_provider(config: ProviderConfig) -> ProviderState:
            return ProviderState(config=config)

        def authenticate(state: ProviderState) -> Tuple[ProviderState, bool]:
            # OAuth flow...
            return state.with_authenticated(True), True

        def sync_library(state: ProviderState) -> Tuple[ProviderState, List[Tuple[str, Dict]]]:
            # Fetch tracks from API...
            tracks = [("track_id_123", {"title": "Song", "artist": "Artist"})]
            return state.with_sync_time(), tracks
    """

    def init_provider(config: ProviderConfig) -> ProviderState:
        """Initialize provider state.

        Args:
            config: Provider configuration

        Returns:
            Initial provider state
        """
        ...

    def authenticate(state: ProviderState) -> Tuple[ProviderState, bool]:
        """Authenticate with the provider.

        For OAuth providers, this may trigger a browser flow.
        For local providers, this is a no-op.

        Args:
            state: Current provider state

        Returns:
            (new_state, success)
        """
        ...

    def sync_library(state: ProviderState) -> Tuple[ProviderState, List[Tuple[str, Dict[str, Any]]]]:
        """Sync library from provider and return track data.

        Returns list of (provider_id, metadata) tuples where:
        - provider_id: Provider's unique track identifier
        - metadata: Dictionary with track metadata (title, artist, album, etc.)

        Args:
            state: Current provider state

        Returns:
            (new_state, [(provider_id, metadata), ...])

        Example:
            state, tracks = sync_library(state)
            # tracks = [
            #     ("123456", {"title": "Song 1", "artist": "Artist A", "duration": 180.0}),
            #     ("789012", {"title": "Song 2", "artist": "Artist B", "duration": 240.0}),
            # ]
        """
        ...

    def search(state: ProviderState, query: str) -> Tuple[ProviderState, List[Tuple[str, Dict[str, Any]]]]:
        """Search for tracks in the provider's catalog.

        Args:
            state: Current provider state
            query: Search query string

        Returns:
            (new_state, [(provider_id, metadata), ...])
        """
        ...

    def get_stream_url(state: ProviderState, provider_id: str) -> Optional[str]:
        """Get playback URL for a track.

        Args:
            state: Current provider state
            provider_id: Provider's track ID

        Returns:
            Stream URL for MPV or None if unavailable
        """
        ...

    def get_playlists(state: ProviderState, full: bool = False) -> Tuple[ProviderState, List[Dict[str, Any]]]:
        """Get user's playlists from provider.

        Args:
            state: Current provider state
            full: If True, bypass optimizations and fetch all data (default: False)

        Returns:
            (new_state, [{"id": "...", "name": "...", "track_count": N}, ...])
        """
        ...

    def get_playlist_tracks(state: ProviderState, playlist_id: str) -> Tuple[ProviderState, List[Tuple[str, Dict[str, Any]]], Optional[str]]:
        """Get tracks in a specific playlist.

        Args:
            state: Current provider state
            playlist_id: Provider's playlist ID

        Returns:
            (new_state, [(provider_id, metadata), ...], created_at_timestamp)
            created_at_timestamp is ISO 8601 string or None if not available
        """
        ...


# Type aliases for convenience
TrackMetadata = Dict[str, Any]  # {title, artist, album, duration, ...}
TrackData = Tuple[str, TrackMetadata]  # (provider_id, metadata)
TrackList = List[TrackData]  # [(provider_id, metadata), ...]


# Helper functions for working with track metadata

def normalize_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize track metadata to standard format.

    Ensures consistent field names and types across providers.

    Args:
        metadata: Raw metadata from provider

    Returns:
        Normalized metadata dictionary
    """
    normalized = {}

    # Title (required)
    if 'title' in metadata:
        normalized['title'] = str(metadata['title']).strip()

    # Artist (required)
    if 'artist' in metadata:
        normalized['artist'] = str(metadata['artist']).strip()
    elif 'user' in metadata and isinstance(metadata['user'], dict):
        # SoundCloud format
        normalized['artist'] = str(metadata['user'].get('username', '')).strip()

    # Remix artist (optional)
    if 'remix_artist' in metadata:
        normalized['remix_artist'] = str(metadata['remix_artist']).strip()

    # Album (optional)
    if 'album' in metadata:
        normalized['album'] = str(metadata['album']).strip()

    # Genre (optional)
    if 'genre' in metadata:
        normalized['genre'] = str(metadata['genre']).strip()

    # Year (optional)
    if 'year' in metadata:
        try:
            normalized['year'] = int(metadata['year'])
        except (ValueError, TypeError):
            pass

    # Duration in seconds (optional)
    if 'duration' in metadata:
        try:
            # Convert to float seconds
            duration = float(metadata['duration'])
            # Some providers give milliseconds
            if duration > 10000:  # Likely milliseconds
                duration = duration / 1000.0
            normalized['duration'] = duration
        except (ValueError, TypeError):
            pass

    # BPM (optional)
    if 'bpm' in metadata:
        try:
            normalized['bpm'] = float(metadata['bpm'])
        except (ValueError, TypeError):
            pass

    # Key (optional)
    if 'key' in metadata:
        normalized['key'] = str(metadata['key']).strip()

    return normalized


def metadata_to_track_dict(provider_id: str, metadata: Dict[str, Any], provider: str) -> Dict[str, Any]:
    """Convert provider metadata to database track dictionary.

    Args:
        provider_id: Provider's track ID
        metadata: Normalized metadata
        provider: Provider name ('soundcloud', 'spotify', etc.)

    Returns:
        Dictionary suitable for database insertion
    """
    track_dict = {
        f'{provider}_id': provider_id,
        'title': metadata.get('title'),
        'artist': metadata.get('artist'),
        'remix_artist': metadata.get('remix_artist'),
        'album': metadata.get('album'),
        'genre': metadata.get('genre'),
        'year': metadata.get('year'),
        'duration': metadata.get('duration'),
        'bpm': metadata.get('bpm'),
        'key_signature': metadata.get('key'),
    }

    # Remove None values
    return {k: v for k, v in track_dict.items() if v is not None}
