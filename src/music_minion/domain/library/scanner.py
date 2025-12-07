"""
Music library scanning and search operations.

Handles scanning directories for music files, filtering tracks,
and generating library statistics.
"""

import random
from pathlib import Path
from typing import Any, Optional

from music_minion.core.config import Config

from .metadata import extract_track_metadata, format_duration, format_size
from .models import Track


def is_supported_format(local_path: Path, supported_formats: list[str]) -> bool:
    """Check if file format is supported."""
    return local_path.suffix.lower() in supported_formats


def scan_directory(
    directory: Path, config: Config, progress_callback=None
) -> list[Track]:
    """Scan a directory for music files and extract metadata.

    Args:
        directory: Directory to scan
        config: Configuration object
        progress_callback: Optional callback function(local_path, track) for progress updates

    Returns:
        List of Track objects
    """
    tracks = []

    try:
        # Smart glob: only traverse music files (2x faster than rglob("*"))
        files = []
        if config.music.scan_recursive:
            # Only glob music file extensions
            for ext in config.music.supported_formats:
                files.extend(directory.rglob(f"*{ext}"))
        else:
            # Only iterate music files in immediate directory
            for ext in config.music.supported_formats:
                files.extend(directory.glob(f"*{ext}"))

        for local_path in files:
            # Already filtered by extension, just check if it's a file
            if local_path.is_file():
                try:
                    track = extract_track_metadata(str(local_path))
                    tracks.append(track)

                    # Call progress callback if provided
                    if progress_callback:
                        progress_callback(str(local_path), track)

                except Exception as e:
                    print(f"Error processing {local_path}: {e}")

    except PermissionError:
        print(f"Permission denied accessing: {directory}")
    except Exception as e:
        print(f"Error scanning directory {directory}: {e}")

    return tracks


def scan_music_library(
    config: Config, show_progress: bool = True, progress_callback=None
) -> list[Track]:
    """Scan all configured library paths for music files.

    Args:
        config: Configuration object
        show_progress: Whether to print progress messages (deprecated, use progress_callback)
        progress_callback: Optional callback function(local_path, track) for progress updates

    Returns:
        List of Track objects
    """
    all_tracks = []

    if show_progress:
        print("Scanning music library...")

    for library_path in config.music.library_paths:
        path = Path(library_path).expanduser()
        if not path.exists():
            print(f"Warning: Library path does not exist: {path}")
            continue

        if show_progress:
            print(f"Scanning: {path}")

        tracks = scan_directory(path, config, progress_callback=progress_callback)
        all_tracks.extend(tracks)

    if show_progress:
        print(f"Library scan complete: {len(all_tracks)} tracks found")

    return all_tracks


def scan_music_library_optimized(
    config: Config, show_progress: bool = True
) -> list[Track]:
    """Optimized library scan that skips unchanged files.

    First scan: Normal speed (must extract all metadata)
    Subsequent scans: 10-50x faster (only process new/changed files)

    Args:
        config: Configuration object
        show_progress: Whether to print progress messages

    Returns:
        List of Track objects (only new/changed files)
    """
    import os
    from loguru import logger
    from music_minion.core import database

    # Load known files from database with mtimes
    known_files = {}
    with database.get_db_connection() as conn:
        cursor = conn.execute("""
            SELECT local_path, file_mtime
            FROM tracks
            WHERE local_path IS NOT NULL AND source = 'local'
        """)
        for row in cursor.fetchall():
            known_files[row["local_path"]] = row["file_mtime"]

    logger.info(f"Database has {len(known_files)} known files")

    all_tracks = []
    skipped = 0
    processed = 0

    for library_path in config.music.library_paths:
        path = Path(library_path).expanduser()
        if not path.exists():
            if show_progress:
                print(f"Warning: Library path does not exist: {path}")
            continue

        # Get all music files using smart glob
        files = []
        for ext in config.music.supported_formats:
            if config.music.scan_recursive:
                files.extend(path.rglob(f"*{ext}"))
            else:
                files.extend(path.glob(f"*{ext}"))

        if show_progress:
            print(f"Found {len(files)} music files in {path}")

        # Process files
        for file_path in files:
            if not file_path.is_file():
                continue

            file_path_str = str(file_path)

            # Check if file is unchanged
            if file_path_str in known_files:
                current_mtime = os.stat(file_path_str).st_mtime
                stored_mtime = known_files[file_path_str]

                if stored_mtime and current_mtime <= stored_mtime:
                    # File unchanged, skip metadata extraction
                    skipped += 1
                    continue

            # New or changed file - extract metadata
            try:
                track = extract_track_metadata(file_path_str)
                all_tracks.append(track)
                processed += 1

                if show_progress and processed % 100 == 0:
                    print(f"  Processed {processed} files...")

            except Exception as e:
                logger.error(f"Error processing {file_path_str}: {e}")

    if show_progress:
        print(f"\nScan complete:")
        print(f"  Processed: {processed} new/changed files")
        print(f"  Skipped: {skipped} unchanged files")

    logger.info(f"Scan stats - processed: {processed}, skipped: {skipped}")

    return all_tracks


def get_random_track(tracks: list[Track]) -> Optional[Track]:
    """Get a random track from the library."""
    return random.choice(tracks) if tracks else None


def search_tracks(tracks: list[Track], query: str) -> list[Track]:
    """Search tracks by title, artist, album, or key."""
    query = query.lower()
    results = []

    for track in tracks:
        # Search in various fields
        # Use string split instead of Path object for better performance in tight loop
        filename = track.local_path.split("/")[-1] if track.local_path else ""
        search_fields = [
            track.title or "",
            track.artist or "",
            track.album or "",
            track.genre or "",
            track.key or "",
            filename,
        ]

        if any(query in field.lower() for field in search_fields):
            results.append(track)

    return results


def get_tracks_by_key(tracks: list[Track], key: str) -> list[Track]:
    """Get all tracks in a specific key."""
    key = key.lower()
    return [track for track in tracks if track.key and key in track.key.lower()]


def get_tracks_by_bpm_range(
    tracks: list[Track], min_bpm: float, max_bpm: float
) -> list[Track]:
    """Get tracks within a BPM range."""
    return [track for track in tracks if track.bpm and min_bpm <= track.bpm <= max_bpm]


def get_tracks_by_artist(tracks: list[Track], artist: str) -> list[Track]:
    """Get all tracks by a specific artist."""
    artist = artist.lower()
    return [
        track for track in tracks if track.artist and artist in track.artist.lower()
    ]


def get_tracks_by_album(tracks: list[Track], album: str) -> list[Track]:
    """Get all tracks from a specific album."""
    album = album.lower()
    return [track for track in tracks if track.album and album in track.album.lower()]


def get_library_stats(tracks: list[Track]) -> dict[str, Any]:
    """Get statistics about the music library."""
    if not tracks:
        return {
            "total_tracks": 0,
            "total_duration": 0,
            "total_size": 0,
            "artists": 0,
            "albums": 0,
            "formats": {},
            "keys": {},
            "avg_bpm": None,
            "tracks_with_bpm": 0,
            "tracks_with_key": 0,
        }

    total_duration = sum(track.duration or 0 for track in tracks)
    total_size = sum(track.file_size for track in tracks)

    artists = set()
    albums = set()
    formats = {}
    keys = {}
    bpm_values = []

    tracks_with_bpm = 0
    tracks_with_key = 0

    for track in tracks:
        if track.artist:
            artists.add(track.artist)
        if track.album:
            albums.add(track.album)
        if track.format:
            formats[track.format] = formats.get(track.format, 0) + 1
        if track.key:
            keys[track.key] = keys.get(track.key, 0) + 1
            tracks_with_key += 1
        if track.bpm:
            bpm_values.append(track.bpm)
            tracks_with_bpm += 1

    avg_bpm = sum(bpm_values) / len(bpm_values) if bpm_values else None

    return {
        "total_tracks": len(tracks),
        "total_duration": total_duration,
        "total_duration_str": format_duration(total_duration),
        "total_size": total_size,
        "total_size_str": format_size(total_size),
        "artists": len(artists),
        "albums": len(albums),
        "formats": formats,
        "keys": keys,
        "avg_bpm": avg_bpm,
        "tracks_with_bpm": tracks_with_bpm,
        "tracks_with_key": tracks_with_key,
    }


def get_track_id_from_track(track: Track) -> Optional[int]:
    """Find database track ID from Track object (multi-source support).

    Checks provider IDs first (SoundCloud, Spotify, YouTube), then falls back
    to local_path for local files.

    Args:
        track: Track object to look up

    Returns:
        Database track ID if found, None otherwise
    """
    from music_minion.core import database

    # Check provider IDs first
    if track.soundcloud_id:
        db_track = database.get_track_by_provider_id("soundcloud", track.soundcloud_id)
        if db_track:
            return db_track["id"]

    if track.spotify_id:
        db_track = database.get_track_by_provider_id("spotify", track.spotify_id)
        if db_track:
            return db_track["id"]

    if track.youtube_id:
        db_track = database.get_track_by_provider_id("youtube", track.youtube_id)
        if db_track:
            return db_track["id"]

    # Fall back to local path for local files
    if track.local_path:
        db_track = database.get_track_by_path(track.local_path)
        if db_track:
            return db_track["id"]

    return None
