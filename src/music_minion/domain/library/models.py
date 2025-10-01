"""
Music library domain models.

Contains data structures for representing music tracks.
"""

from typing import Optional, NamedTuple


class Track(NamedTuple):
    """Represents a music track with metadata."""
    file_path: str
    title: Optional[str] = None
    artist: Optional[str] = None
    album: Optional[str] = None
    genre: Optional[str] = None
    year: Optional[int] = None
    duration: Optional[float] = None  # in seconds
    bitrate: Optional[int] = None
    file_size: int = 0
    format: Optional[str] = None
    key: Optional[str] = None  # Musical key (e.g., "Am", "C#m")
    bpm: Optional[float] = None  # Beats per minute
