"""
Music library scanning and search operations.

Handles scanning directories for music files, filtering tracks,
and generating library statistics.
"""

import random
from pathlib import Path
from typing import List, Optional, Dict, Any

from music_minion.core.config import Config
from .models import Track
from .metadata import extract_track_metadata, format_duration, format_size


def is_supported_format(file_path: Path, supported_formats: List[str]) -> bool:
    """Check if file format is supported."""
    return file_path.suffix.lower() in supported_formats


def scan_directory(directory: Path, config: Config) -> List[Track]:
    """Scan a directory for music files and extract metadata."""
    tracks = []

    try:
        # Get all files if recursive, otherwise just immediate files
        if config.music.scan_recursive:
            files = directory.rglob('*')
        else:
            files = directory.iterdir()

        for file_path in files:
            if file_path.is_file() and is_supported_format(file_path, config.music.supported_formats):
                try:
                    track = extract_track_metadata(str(file_path))
                    tracks.append(track)
                except Exception as e:
                    print(f"Error processing {file_path}: {e}")

    except PermissionError:
        print(f"Permission denied accessing: {directory}")
    except Exception as e:
        print(f"Error scanning directory {directory}: {e}")

    return tracks


def scan_music_library(config: Config, show_progress: bool = True) -> List[Track]:
    """Scan all configured library paths for music files."""
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

        tracks = scan_directory(path, config)
        all_tracks.extend(tracks)

    if show_progress:
        print(f"Library scan complete: {len(all_tracks)} tracks found")

    return all_tracks


def get_random_track(tracks: List[Track]) -> Optional[Track]:
    """Get a random track from the library."""
    return random.choice(tracks) if tracks else None


def search_tracks(tracks: List[Track], query: str) -> List[Track]:
    """Search tracks by title, artist, album, or key."""
    query = query.lower()
    results = []

    for track in tracks:
        # Search in various fields
        search_fields = [
            track.title or '',
            track.artist or '',
            track.album or '',
            track.genre or '',
            track.key or '',
            Path(track.file_path).name
        ]

        if any(query in field.lower() for field in search_fields):
            results.append(track)

    return results


def get_tracks_by_key(tracks: List[Track], key: str) -> List[Track]:
    """Get all tracks in a specific key."""
    key = key.lower()
    return [track for track in tracks
            if track.key and key in track.key.lower()]


def get_tracks_by_bpm_range(tracks: List[Track], min_bpm: float, max_bpm: float) -> List[Track]:
    """Get tracks within a BPM range."""
    return [track for track in tracks
            if track.bpm and min_bpm <= track.bpm <= max_bpm]


def get_tracks_by_artist(tracks: List[Track], artist: str) -> List[Track]:
    """Get all tracks by a specific artist."""
    artist = artist.lower()
    return [track for track in tracks
            if track.artist and artist in track.artist.lower()]


def get_tracks_by_album(tracks: List[Track], album: str) -> List[Track]:
    """Get all tracks from a specific album."""
    album = album.lower()
    return [track for track in tracks
            if track.album and album in track.album.lower()]


def get_library_stats(tracks: List[Track]) -> Dict[str, Any]:
    """Get statistics about the music library."""
    if not tracks:
        return {
            'total_tracks': 0,
            'total_duration': 0,
            'total_size': 0,
            'artists': 0,
            'albums': 0,
            'formats': {},
            'keys': {},
            'avg_bpm': None,
            'tracks_with_bpm': 0,
            'tracks_with_key': 0
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
        'total_tracks': len(tracks),
        'total_duration': total_duration,
        'total_duration_str': format_duration(total_duration),
        'total_size': total_size,
        'total_size_str': format_size(total_size),
        'artists': len(artists),
        'albums': len(albums),
        'formats': formats,
        'keys': keys,
        'avg_bpm': avg_bpm,
        'tracks_with_bpm': tracks_with_bpm,
        'tracks_with_key': tracks_with_key
    }
