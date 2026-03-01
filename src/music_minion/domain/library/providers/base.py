"""Base provider interface for music providers (SoundCloud, Spotify, etc.).

This module defines common interfaces for streaming music providers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class ProviderTrack:
    """Normalized track from any provider."""

    provider_id: str  # soundcloud_id, spotify_id, etc.
    title: str
    artist: str
    genre: Optional[str] = None
    bpm: Optional[float] = None
    duration: Optional[float] = None  # seconds
    source_url: Optional[str] = None  # permalink for streaming


@dataclass
class ProviderPlaylist:
    """Normalized playlist from any provider."""

    provider_id: str
    name: str
    track_count: int


class Provider(ABC):
    """Base interface for music providers (SoundCloud, Spotify, etc.)."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name for database source column."""
        ...

    @abstractmethod
    def get_stream_url(self, provider_id: str) -> Optional[str]:
        """Get playable stream URL for a track."""
        ...

    @abstractmethod
    def get_playlists(self) -> list[ProviderPlaylist]:
        """Get user's playlists."""
        ...

    @abstractmethod
    def get_playlist_tracks(self, playlist_id: str) -> list[ProviderTrack]:
        """Get tracks in a playlist."""
        ...

    @abstractmethod
    def get_liked_tracks(
        self, since_timestamp: Optional[str] = None
    ) -> list[ProviderTrack]:
        """Get user's liked tracks, optionally since a timestamp for delta sync."""
        ...
