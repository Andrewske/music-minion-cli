"""
Music metadata extraction and track information utilities.

Handles reading metadata from audio files using Mutagen,
and provides utility functions for displaying track information.
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from mutagen import File as MutagenFile
from mutagen.id3 import ID3NoHeaderError

from .models import Track


def get_tag_value(audio_file: MutagenFile, tag_names: List[str]) -> Optional[str]:
    """Get tag value, trying multiple possible tag names."""
    for tag_name in tag_names:
        value = audio_file.get(tag_name)
        if value:
            # Handle different formats
            if isinstance(value, list) and value:
                return str(value[0])
            return str(value)
    return None


def extract_metadata_from_filename(local_path: str) -> Dict[str, Any]:
    """Extract basic info from filename as fallback."""
    path = Path(local_path)
    title = path.stem
    artist = None

    # Try to parse "Artist - Title" format
    if " - " in title:
        parts = title.split(" - ", 1)
        if len(parts) == 2:
            artist = parts[0].strip()
            title = parts[1].strip()

    # Get file size
    try:
        file_size = os.path.getsize(local_path)
    except OSError:
        file_size = 0

    return {
        "title": title,
        "artist": artist,
        "format": path.suffix.lower(),
        "file_size": file_size,
    }


def extract_track_metadata(local_path: str) -> Track:
    """Extract metadata from audio file using mutagen."""
    try:
        audio_file = MutagenFile(local_path)
        if audio_file is None:
            # File couldn't be read by mutagen, use filename
            fallback = extract_metadata_from_filename(local_path)
            return Track(
                local_path=local_path,
                title=fallback["title"],
                artist=fallback["artist"],
                format=fallback["format"],
                file_size=fallback["file_size"],
            )

        # Extract common metadata
        # ID3 (MP3), MP4, and Vorbis/Opus tags (lowercase)
        title = get_tag_value(audio_file, ["TIT2", "\xa9nam", "TITLE", "title"])
        artist = get_tag_value(audio_file, ["TPE1", "\xa9ART", "ARTIST", "artist"])
        remix_artist = get_tag_value(
            audio_file, ["TPE4", "TPE2", "albumartist"]
        )  # Remix artist (TPE4) or Album artist (TPE2/albumartist)
        album = get_tag_value(audio_file, ["TALB", "\xa9alb", "ALBUM", "album"])
        genre = get_tag_value(audio_file, ["TCON", "\xa9gen", "GENRE", "genre"])

        # Extract DJ metadata (ID3, MP4, Vorbis/Opus)
        key = get_tag_value(audio_file, ["TKEY", "KEY", "INITIAL_KEY", "\xa9key", "key"])
        bpm_str = get_tag_value(
            audio_file, ["TBPM", "BPM", "BEATS_PER_MINUTE", "\xa9bpm", "bpm"]
        )
        bpm = None
        if bpm_str:
            try:
                bpm = float(bpm_str)
            except (ValueError, TypeError):
                pass

        # Extract year (ID3, MP4, Vorbis/Opus)
        year = None
        year_str = get_tag_value(audio_file, ["TDRC", "\xa9day", "DATE", "YEAR", "date", "year"])
        if year_str:
            try:
                # Handle various year formats
                year_str = str(year_str).split("-")[0]  # Take first part of date
                year = int(year_str)
            except (ValueError, TypeError):
                pass

        # Extract technical info
        duration = None
        bitrate = None
        if hasattr(audio_file, "info"):
            duration = getattr(audio_file.info, "length", None)
            bitrate = getattr(audio_file.info, "bitrate", None)

        # Get file format and size
        format = Path(local_path).suffix.lower()
        file_size = os.path.getsize(local_path)

        # Fallback to filename if no title
        if not title:
            title = Path(local_path).stem

        return Track(
            local_path=local_path,
            title=title,
            artist=artist,
            remix_artist=remix_artist,
            album=album,
            genre=genre,
            year=year,
            duration=duration,
            bitrate=bitrate,
            file_size=file_size,
            format=format,
            key=key,
            bpm=bpm,
        )

    except (ID3NoHeaderError, Exception) as e:
        print(f"Warning: Could not read metadata from {local_path}: {e}")
        fallback = extract_metadata_from_filename(local_path)
        return Track(
            local_path=local_path,
            title=fallback["title"],
            artist=fallback["artist"],
            format=fallback["format"],
            file_size=fallback["file_size"],
        )


def get_display_name(track: Track) -> str:
    """Get a display-friendly name for the track."""
    if track.artist and track.title:
        return f"{track.artist} - {track.title}"
    elif track.title:
        return track.title
    elif track.local_path:
        return Path(track.local_path).stem
    else:
        return "<Unknown Track>"


def get_duration_str(track: Track) -> str:
    """Get duration as a formatted string (MM:SS)."""
    if not track.duration:
        return "??:??"

    minutes = int(track.duration // 60)
    seconds = int(track.duration % 60)
    return f"{minutes:02d}:{seconds:02d}"


def get_dj_info(track: Track) -> str:
    """Get DJ-relevant info (key, BPM, year) as a formatted string."""
    info_parts = []

    if track.year:
        info_parts.append(str(track.year))
    if track.key:
        info_parts.append(track.key)
    if track.bpm:
        info_parts.append(f"{track.bpm:.0f} BPM")
    if track.genre:
        info_parts.append(track.genre)

    return " • ".join(info_parts) if info_parts else "No DJ metadata"


def format_duration(seconds: float) -> str:
    """Format duration in seconds to human readable string."""
    if seconds == 0:
        return "0:00"

    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes}:{secs:02d}"


def format_size(bytes_size: int) -> str:
    """Format file size in bytes to human readable string."""
    for unit in ["B", "KB", "MB", "GB"]:
        if bytes_size < 1024:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024
    return f"{bytes_size:.1f} TB"
