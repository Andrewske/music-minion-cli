"""
Music metadata extraction and track information utilities.

Handles reading and writing metadata from/to audio files using Mutagen,
and provides utility functions for displaying track information.
"""

import os
import re
import shutil
from pathlib import Path
from typing import Any, Optional

from loguru import logger
from mutagen import File as MutagenFile
from mutagen.id3 import (
    ID3,
    ID3NoHeaderError,
    TALB,
    TBPM,
    TCON,
    TDRC,
    TIT2,
    TKEY,
    TPE1,
    TXXX,
    COMM,
)
from mutagen.mp4 import MP4
from mutagen.oggopus import OggOpus
from mutagen.oggvorbis import OggVorbis

from .models import Track


def get_tag_value(audio_file: MutagenFile, tag_names: list[str]) -> Optional[str]:
    """Get tag value, trying multiple possible tag names."""
    for tag_name in tag_names:
        try:
            value = audio_file.get(tag_name)
            if value:
                # Handle different formats
                if isinstance(value, list) and value:
                    return str(value[0])
                return str(value)
        except (KeyError, ValueError):
            # Some formats (like Vorbis) raise ValueError for non-existent keys
            continue
    return None


def extract_metadata_from_filename(local_path: str) -> dict[str, Any]:
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
        key = get_tag_value(
            audio_file, ["TKEY", "KEY", "INITIAL_KEY", "initialkey", "\xa9key", "key"]
        )
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
        year_str = get_tag_value(
            audio_file, ["TDRC", "\xa9day", "DATE", "YEAR", "date", "year"]
        )
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


def write_metadata_to_file(
    local_path: str,
    title: Optional[str] = None,
    artist: Optional[str] = None,
    album: Optional[str] = None,
    genre: Optional[str] = None,
    year: Optional[int] = None,
    bpm: Optional[float] = None,
    key: Optional[str] = None,
) -> bool:
    """Write metadata fields to audio file using atomic writes.

    Supports MP3 (ID3), M4A (MP4), Opus, and OGG files.

    Args:
        local_path: Path to the audio file
        title: Track title
        artist: Track artist
        album: Album name
        genre: Genre
        year: Release year
        bpm: Beats per minute
        key: Musical key (e.g., "Am", "C#m")

    Returns:
        True if successful, False otherwise
    """
    if not os.path.exists(local_path):
        logger.warning(f"File not found: {local_path}")
        return False

    # Use atomic write: copy to temp, modify, replace
    temp_path = local_path + ".tmp"

    try:
        # Copy original to temp
        shutil.copy2(local_path, temp_path)

        # Load temp file
        audio = MutagenFile(temp_path)
        if audio is None:
            logger.warning(f"Could not open file: {local_path}")
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return False

        # Determine format and write tags
        if isinstance(audio.tags, ID3) or hasattr(audio, "ID3"):
            _write_id3_metadata(audio, title, artist, album, genre, year, bpm, key)
        elif isinstance(audio, MP4):
            _write_mp4_metadata(audio, title, artist, album, genre, year, bpm, key)
        elif isinstance(audio, (OggOpus, OggVorbis)):
            _write_vorbis_metadata(audio, title, artist, album, genre, year, bpm, key)
        else:
            logger.warning(f"Unsupported format for metadata writing: {local_path}")
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return False

        # Save changes
        audio.save()

        # Atomic replace
        os.replace(temp_path, local_path)
        return True

    except Exception as e:
        logger.exception(f"Error writing metadata to {local_path}: {e}")
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass
        return False


def _write_id3_metadata(
    audio: MutagenFile,
    title: Optional[str],
    artist: Optional[str],
    album: Optional[str],
    genre: Optional[str],
    year: Optional[int],
    bpm: Optional[float],
    key: Optional[str],
) -> None:
    """Write metadata to ID3 tags (MP3)."""
    # Ensure tags exist
    if audio.tags is None:
        audio.add_tags()

    tags = audio.tags

    if title is not None:
        tags["TIT2"] = TIT2(encoding=3, text=title)
    if artist is not None:
        tags["TPE1"] = TPE1(encoding=3, text=artist)
    if album is not None:
        tags["TALB"] = TALB(encoding=3, text=album)
    if genre is not None:
        tags["TCON"] = TCON(encoding=3, text=genre)
    if year is not None:
        tags["TDRC"] = TDRC(encoding=3, text=str(year))
    if bpm is not None:
        tags["TBPM"] = TBPM(encoding=3, text=str(int(bpm)))
    if key is not None:
        tags["TKEY"] = TKEY(encoding=3, text=key)


def _write_mp4_metadata(
    audio: MP4,
    title: Optional[str],
    artist: Optional[str],
    album: Optional[str],
    genre: Optional[str],
    year: Optional[int],
    bpm: Optional[float],
    key: Optional[str],
) -> None:
    """Write metadata to MP4/M4A tags."""
    if title is not None:
        audio["\xa9nam"] = [title]
    if artist is not None:
        audio["\xa9ART"] = [artist]
    if album is not None:
        audio["\xa9alb"] = [album]
    if genre is not None:
        audio["\xa9gen"] = [genre]
    if year is not None:
        audio["\xa9day"] = [str(year)]
    if bpm is not None:
        audio["tmpo"] = [int(bpm)]
    # Note: No standard key field for MP4, using custom field
    if key is not None:
        audio["----:com.apple.iTunes:INITIALKEY"] = key.encode("utf-8")


def _write_vorbis_metadata(
    audio: MutagenFile,
    title: Optional[str],
    artist: Optional[str],
    album: Optional[str],
    genre: Optional[str],
    year: Optional[int],
    bpm: Optional[float],
    key: Optional[str],
) -> None:
    """Write metadata to Vorbis comments (Opus, OGG)."""
    if title is not None:
        audio["TITLE"] = title
    if artist is not None:
        audio["ARTIST"] = artist
    if album is not None:
        audio["ALBUM"] = album
    if genre is not None:
        audio["GENRE"] = genre
    if year is not None:
        audio["DATE"] = str(year)
    if bpm is not None:
        audio["BPM"] = str(int(bpm))
    if key is not None:
        audio["INITIALKEY"] = key


def strip_elo_from_comment(comment: str | None) -> str:
    """Strip ELO rating prefix from comment, returning clean comment."""
    if not comment:
        return ""

    # Regex to match "NNNN - " or "NNNN" at start
    pattern = r"^\d{4}(?:\s*-\s*)?"
    return re.sub(pattern, "", comment).strip()


def format_comment_with_elo(elo: float, existing_comment: str | None) -> str:
    """Format comment with ELO rating prefix."""
    # Clamp ELO to 0-9999 range and round to int
    clamped_elo = max(0, min(9999, int(round(elo))))

    # Zero-pad to 4 digits
    elo_prefix = f"{clamped_elo:04d}"

    # Strip any existing ELO prefix from comment
    clean_comment = strip_elo_from_comment(existing_comment)

    # Combine with existing comment if present
    if clean_comment:
        return f"{elo_prefix} - {clean_comment}"
    else:
        return elo_prefix


def _write_elo_id3(
    audio: MutagenFile,
    global_elo: float | None,
    playlist_elo: float | None,
    update_comment: bool,
) -> None:
    """Write ELO ratings to ID3 tags (MP3)."""
    # Ensure tags exist
    if audio.tags is None:
        audio.add_tags()

    tags = audio.tags

    if global_elo is not None:
        tags["TXXX:GLOBAL_ELO"] = TXXX(
            encoding=3, desc="GLOBAL_ELO", text=str(global_elo)
        )
    if playlist_elo is not None:
        tags["TXXX:PLAYLIST_ELO"] = TXXX(
            encoding=3, desc="PLAYLIST_ELO", text=str(playlist_elo)
        )

    if update_comment:
        # Get existing comment
        existing_comment = None
        if "COMM" in tags:
            existing_comment = str(tags["COMM"])

        # Format with ELO (use global_elo if available, else playlist_elo)
        elo_to_use = global_elo if global_elo is not None else playlist_elo
        if elo_to_use is not None:
            new_comment = format_comment_with_elo(elo_to_use, existing_comment)
            tags["COMM"] = COMM(encoding=3, lang="eng", desc="", text=new_comment)


def _write_elo_mp4(
    audio: MP4,
    global_elo: float | None,
    playlist_elo: float | None,
    update_comment: bool,
) -> None:
    """Write ELO ratings to MP4 tags."""
    if global_elo is not None:
        audio["----:com.apple.iTunes:GLOBAL_ELO"] = str(global_elo).encode("utf-8")
    if playlist_elo is not None:
        audio["----:com.apple.iTunes:PLAYLIST_ELO"] = str(playlist_elo).encode("utf-8")

    if update_comment:
        # Get existing comment
        existing_comment = None
        if "\xa9cmt" in audio:
            existing_comment = str(audio["\xa9cmt"][0])

        # Format with ELO (use global_elo if available, else playlist_elo)
        elo_to_use = global_elo if global_elo is not None else playlist_elo
        if elo_to_use is not None:
            new_comment = format_comment_with_elo(elo_to_use, existing_comment)
            audio["\xa9cmt"] = [new_comment]


def _write_elo_vorbis(
    audio: MutagenFile,
    global_elo: float | None,
    playlist_elo: float | None,
    update_comment: bool,
) -> None:
    """Write ELO ratings to Vorbis comments (Opus, OGG)."""
    if global_elo is not None:
        audio["GLOBAL_ELO"] = str(global_elo)
    if playlist_elo is not None:
        audio["PLAYLIST_ELO"] = str(playlist_elo)

    if update_comment:
        # Get existing comment
        existing_comment = audio.get("COMMENT", [""])[0]

        # Format with ELO (use global_elo if available, else playlist_elo)
        elo_to_use = global_elo if global_elo is not None else playlist_elo
        if elo_to_use is not None:
            new_comment = format_comment_with_elo(elo_to_use, existing_comment)
            audio["COMMENT"] = new_comment


def write_elo_to_file(
    local_path: str,
    global_elo: float | None = None,
    playlist_elo: float | None = None,
    update_comment: bool = False,
) -> bool:
    """Write ELO ratings to audio file metadata using atomic writes.

    Skips writing if ELO values are None or 1500 (unrated default).

    Args:
        local_path: Path to the audio file
        global_elo: Global ELO rating
        playlist_elo: Playlist-specific ELO rating
        update_comment: Whether to update comment field with ELO prefix

    Returns:
        True if successful, False otherwise
    """
    # Skip if no ELO values provided or both are unrated (1500)
    if (global_elo is None or global_elo == 1500) and (
        playlist_elo is None or playlist_elo == 1500
    ):
        return True  # Not an error, just nothing to do

    if not os.path.exists(local_path):
        logger.warning(f"File not found: {local_path}")
        return False

    # Use atomic write: copy to temp, modify, replace
    temp_path = local_path + ".tmp"

    try:
        # Copy original to temp
        shutil.copy2(local_path, temp_path)

        # Load temp file
        audio = MutagenFile(temp_path)
        if audio is None:
            logger.warning(f"Could not open file: {local_path}")
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return False

        # Determine format and write ELO tags
        if isinstance(audio.tags, ID3) or hasattr(audio, "ID3"):
            _write_elo_id3(audio, global_elo, playlist_elo, update_comment)
        elif isinstance(audio, MP4):
            _write_elo_mp4(audio, global_elo, playlist_elo, update_comment)
        elif isinstance(audio, (OggOpus, OggVorbis)):
            _write_elo_vorbis(audio, global_elo, playlist_elo, update_comment)
        else:
            logger.warning(f"Unsupported format for ELO writing: {local_path}")
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return False

        # Save changes
        audio.save()

        # Atomic replace
        os.replace(temp_path, local_path)
        return True

    except Exception as e:
        logger.exception(f"Error writing ELO to {local_path}: {e}")
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass
        return False
