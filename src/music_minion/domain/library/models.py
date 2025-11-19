"""
Music library domain models.

Contains data structures for representing music tracks.
"""

from typing import Optional, NamedTuple


class Track(NamedTuple):
    """Represents a music track with metadata.

    A track can exist in multiple sources (local file, SoundCloud, Spotify, etc.).
    The file_path field represents the local file path if available (for backward compatibility).
    Provider-specific IDs are stored in separate fields.
    """
    file_path: str  # Local file path (maps to database local_path column)
    title: Optional[str] = None
    artist: Optional[str] = None
    remix_artist: Optional[str] = None  # Remix/edit artist (semicolon-separated)
    album: Optional[str] = None
    genre: Optional[str] = None
    year: Optional[int] = None
    duration: Optional[float] = None  # in seconds
    bitrate: Optional[int] = None
    file_size: int = 0
    format: Optional[str] = None
    key: Optional[str] = None  # Musical key (e.g., "Am", "C#m")
    bpm: Optional[float] = None  # Beats per minute

    # Provider IDs (nullable - track may exist in multiple sources)
    soundcloud_id: Optional[str] = None  # SoundCloud track ID
    spotify_id: Optional[str] = None     # Spotify track ID
    youtube_id: Optional[str] = None     # YouTube video ID
