"""
Playlist import functionality for Music Minion CLI.
Supports importing M3U/M3U8 and Serato .crate playlists.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import urllib.parse

from .database import get_db_connection
from .playlist import create_playlist, add_track_to_playlist


def detect_playlist_format(file_path: Path) -> Optional[str]:
    """
    Detect the format of a playlist file.

    Args:
        file_path: Path to the playlist file

    Returns:
        Format string ('m3u', 'm3u8', 'crate') or None if unknown
    """
    suffix = file_path.suffix.lower()

    if suffix in ['.m3u', '.m3u8']:
        return 'm3u8'  # Treat both as M3U8 (UTF-8)
    elif suffix == '.crate':
        return 'crate'

    return None


def resolve_relative_path(playlist_path: Path, track_path: str, library_root: Path) -> Optional[Path]:
    """
    Resolve a track path from a playlist to an absolute path.

    Handles:
    - Absolute paths
    - Relative paths from playlist location
    - Relative paths from library root
    - URL-encoded paths

    Args:
        playlist_path: Path to the playlist file
        track_path: Track path from playlist (may be relative or absolute)
        library_root: Root directory of music library

    Returns:
        Resolved absolute Path or None if track doesn't exist
    """
    # Decode URL encoding if present
    if '%' in track_path:
        track_path = urllib.parse.unquote(track_path)

    # Convert to Path
    track_path_obj = Path(track_path)

    # If already absolute and exists, return it
    if track_path_obj.is_absolute():
        if track_path_obj.exists():
            return track_path_obj
        # Try making it relative to library root (for cross-platform compatibility)
        # Extract just the relative part
        try:
            # If path starts with a drive letter or root, try to find common music structure
            parts = track_path_obj.parts
            # Look for common music directory names
            for i, part in enumerate(parts):
                if part.lower() in ['music', 'music library', 'itunes', 'serato']:
                    rel_parts = parts[i+1:]
                    if rel_parts:
                        candidate = library_root / Path(*rel_parts)
                        if candidate.exists():
                            return candidate
        except (ValueError, OSError, IndexError):
            # Path operations can fail on invalid paths or permissions issues
            pass
        return None

    # Try relative to playlist directory
    playlist_dir = playlist_path.parent
    candidate = (playlist_dir / track_path_obj).resolve()
    if candidate.exists():
        return candidate

    # Try relative to library root
    candidate = (library_root / track_path_obj).resolve()
    if candidate.exists():
        return candidate

    return None


def _add_tracks_from_paths(
    playlist_id: int,
    playlist_file_path: Path,
    track_paths: List[str],
    library_root: Path
) -> Tuple[int, int, List[str]]:
    """
    Helper function to resolve track paths and add them to a playlist.

    Args:
        playlist_id: ID of the playlist to add tracks to
        playlist_file_path: Path to the playlist file (for relative resolution)
        track_paths: List of track path strings from playlist
        library_root: Root directory of music library

    Returns:
        Tuple of (tracks_added, duplicates_skipped, unresolved_paths)
    """
    tracks_added = 0
    duplicates_skipped = 0
    unresolved_paths = []

    with get_db_connection() as conn:
        cursor = conn.cursor()

        for track_path_str in track_paths:
            # Resolve track path
            resolved_path = resolve_relative_path(playlist_file_path, track_path_str, library_root)

            if resolved_path is None:
                unresolved_paths.append(track_path_str)
                continue

            # Look up track in database by file path
            cursor.execute(
                "SELECT id FROM tracks WHERE file_path = ?",
                (str(resolved_path),)
            )
            row = cursor.fetchone()

            if row:
                track_id = row['id']
                # Add track to playlist
                try:
                    add_track_to_playlist(playlist_id, track_id)
                    tracks_added += 1
                except ValueError:
                    # Track already in playlist, skip
                    duplicates_skipped += 1
            else:
                # Track not in database
                unresolved_paths.append(track_path_str)

    return tracks_added, duplicates_skipped, unresolved_paths


def import_m3u(
    file_path: Path,
    playlist_name: str,
    library_root: Path,
    description: Optional[str] = None
) -> Tuple[int, int, int, List[str]]:
    """
    Import an M3U/M3U8 playlist file.

    Args:
        file_path: Path to the M3U/M3U8 file
        playlist_name: Name for the imported playlist
        library_root: Root directory of music library
        description: Optional description for the playlist

    Returns:
        Tuple of (playlist_id, tracks_added, duplicates_skipped, unresolved_paths)
        - playlist_id: ID of created playlist
        - tracks_added: Number of tracks successfully added
        - duplicates_skipped: Number of duplicate tracks skipped
        - unresolved_paths: List of track paths that couldn't be resolved
    """
    if not file_path.exists():
        raise FileNotFoundError(f"Playlist file not found: {file_path}")

    # Read M3U file
    try:
        # Try UTF-8 first (M3U8 standard)
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except UnicodeDecodeError:
        # Fall back to latin-1 for older M3U files
        with open(file_path, 'r', encoding='latin-1') as f:
            lines = f.readlines()

    # Parse M3U format
    # Format can include:
    # #EXTM3U - header (optional)
    # #EXTINF:duration,artist - title - metadata line (optional)
    # /path/to/track.mp3 - actual track path

    track_paths = []
    for line in lines:
        line = line.strip()

        # Skip empty lines, comments (except #EXTINF), and header
        if not line or line.startswith('#EXTM3U'):
            continue
        if line.startswith('#') and not line.startswith('#EXTINF'):
            continue
        if line.startswith('#EXTINF'):
            continue  # Metadata line, actual path comes next

        track_paths.append(line)

    # Create playlist
    playlist_id = create_playlist(
        name=playlist_name,
        type='manual',
        description=description or f"Imported from {file_path.name}"
    )

    # Resolve and add tracks using helper function
    tracks_added, duplicates_skipped, unresolved_paths = _add_tracks_from_paths(
        playlist_id=playlist_id,
        playlist_file_path=file_path,
        track_paths=track_paths,
        library_root=library_root
    )

    return playlist_id, tracks_added, duplicates_skipped, unresolved_paths


def import_serato_crate(
    file_path: Path,
    playlist_name: str,
    library_root: Path,
    description: Optional[str] = None
) -> Tuple[int, int, int, List[str]]:
    """
    Import a Serato .crate playlist file.

    Args:
        file_path: Path to the .crate file
        playlist_name: Name for the imported playlist
        library_root: Root directory of music library
        description: Optional description for the playlist

    Returns:
        Tuple of (playlist_id, tracks_added, duplicates_skipped, unresolved_paths)
        - playlist_id: ID of created playlist
        - tracks_added: Number of tracks successfully added
        - duplicates_skipped: Number of duplicate tracks skipped
        - unresolved_paths: List of track paths that couldn't be resolved
    """
    if not file_path.exists():
        raise FileNotFoundError(f"Crate file not found: {file_path}")

    try:
        from pyserato.builder import Builder
    except ImportError:
        raise ImportError(
            "pyserato library not installed. Install with: uv pip install pyserato"
        )

    # Parse Serato crate
    try:
        builder = Builder()
        crate = builder.parse_crate(str(file_path))
    except Exception as e:
        raise ValueError(f"Failed to parse Serato crate: {e}")

    # Extract track paths from crate
    # Serato crates store tracks with full paths
    # Note: pyserato object structure may vary by version
    track_paths = []
    try:
        if hasattr(crate, 'tracks'):
            for track in crate.tracks:
                if hasattr(track, 'path'):
                    track_paths.append(track.path)
                elif isinstance(track, str):
                    track_paths.append(track)

        # If no tracks found, the crate structure may be different than expected
        if not track_paths:
            raise ValueError(
                "Could not extract tracks from Serato crate. "
                "The crate file may be in an unsupported format or pyserato library version mismatch."
            )
    except AttributeError as e:
        raise ValueError(
            f"Failed to extract tracks from Serato crate (pyserato API changed?): {e}"
        )

    # Create playlist
    playlist_id = create_playlist(
        name=playlist_name,
        type='manual',
        description=description or f"Imported from {file_path.name}"
    )

    # Resolve and add tracks using helper function
    tracks_added, duplicates_skipped, unresolved_paths = _add_tracks_from_paths(
        playlist_id=playlist_id,
        playlist_file_path=file_path,
        track_paths=track_paths,
        library_root=library_root
    )

    return playlist_id, tracks_added, duplicates_skipped, unresolved_paths


def import_playlist(
    file_path: Path,
    playlist_name: Optional[str] = None,
    library_root: Optional[Path] = None,
    description: Optional[str] = None
) -> Tuple[int, int, int, List[str]]:
    """
    Import a playlist from a file, auto-detecting format.

    Args:
        file_path: Path to the playlist file
        playlist_name: Name for the imported playlist (defaults to filename without extension)
        library_root: Root directory of music library (defaults to ~/Music)
        description: Optional description for the playlist

    Returns:
        Tuple of (playlist_id, tracks_added, duplicates_skipped, unresolved_paths)
        - playlist_id: ID of created playlist
        - tracks_added: Number of tracks successfully added
        - duplicates_skipped: Number of duplicate tracks skipped
        - unresolved_paths: List of track paths that couldn't be resolved

    Raises:
        ValueError: If format is unsupported
        FileNotFoundError: If file doesn't exist
    """
    # Default playlist name to filename without extension
    if playlist_name is None:
        playlist_name = file_path.stem

    # Default library root to ~/Music
    if library_root is None:
        library_root = Path.home() / "Music"

    # Detect format
    format_type = detect_playlist_format(file_path)

    if format_type == 'm3u8':
        return import_m3u(file_path, playlist_name, library_root, description)
    elif format_type == 'crate':
        return import_serato_crate(file_path, playlist_name, library_root, description)
    else:
        raise ValueError(
            f"Unsupported playlist format: {file_path.suffix}. "
            "Supported formats: .m3u, .m3u8, .crate"
        )