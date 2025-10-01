"""Library domain - music file scanning and metadata.

This domain handles:
- Track data models
- Metadata extraction from audio files
- Library scanning and search
- Track filtering and statistics
"""

# Models
from .models import Track

# Metadata extraction and display
from .metadata import (
    get_tag_value,
    extract_metadata_from_filename,
    extract_track_metadata,
    get_display_name,
    get_duration_str,
    get_dj_info,
    format_duration,
    format_size,
)

# Library scanning and search
from .scanner import (
    is_supported_format,
    scan_directory,
    scan_music_library,
    get_random_track,
    search_tracks,
    get_tracks_by_key,
    get_tracks_by_bpm_range,
    get_tracks_by_artist,
    get_tracks_by_album,
    get_library_stats,
)

__all__ = [
    # Models
    "Track",
    # Metadata
    "get_tag_value",
    "extract_metadata_from_filename",
    "extract_track_metadata",
    "get_display_name",
    "get_duration_str",
    "get_dj_info",
    "format_duration",
    "format_size",
    # Scanner
    "is_supported_format",
    "scan_directory",
    "scan_music_library",
    "get_random_track",
    "search_tracks",
    "get_tracks_by_key",
    "get_tracks_by_bpm_range",
    "get_tracks_by_artist",
    "get_tracks_by_album",
    "get_library_stats",
]
