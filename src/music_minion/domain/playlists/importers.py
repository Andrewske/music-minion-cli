"""
Playlist import functionality for Music Minion CLI.
Supports importing M3U/M3U8 and Serato .crate playlists.
"""

import csv
import urllib.parse
from pathlib import Path
from typing import Any, Optional, cast

from music_minion.core.database import get_db_connection

from .crud import add_track_to_playlist, create_playlist


def detect_playlist_format(local_path: Path) -> Optional[str]:
    """
    Detect the format of a playlist file.

    Args:
        local_path: Path to the playlist file

    Returns:
        Format string ('m3u', 'm3u8', 'crate', 'csv') or None if unknown
    """
    suffix = local_path.suffix.lower()

    if suffix in [".m3u", ".m3u8"]:
        return "m3u8"  # Treat both as M3U8 (UTF-8)
    elif suffix == ".crate":
        return "crate"
    elif suffix == ".csv":
        return "csv"

    return None


def resolve_relative_path(
    playlist_path: Path, track_path: str, library_root: Path
) -> Optional[Path]:
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
    if "%" in track_path:
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
                if part.lower() in ["music", "music library", "itunes", "serato"]:
                    rel_parts = parts[i + 1 :]
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
    playlist_local_path: Path,
    track_paths: list[str],
    library_root: Path,
) -> tuple[int, int, list[str]]:
    """
    Helper function to resolve track paths and add them to a playlist.

    Args:
        playlist_id: ID of the playlist to add tracks to
        playlist_local_path: Path to the playlist file (for relative resolution)
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
            resolved_path = resolve_relative_path(
                playlist_local_path, track_path_str, library_root
            )

            if resolved_path is None:
                unresolved_paths.append(track_path_str)
                continue

            # Look up track in database by local file path
            cursor.execute(
                "SELECT id FROM tracks WHERE local_path = ?", (str(resolved_path),)
            )
            row = cursor.fetchone()

            if row:
                track_id = row["id"]
                # Add track to playlist
                if add_track_to_playlist(playlist_id, track_id):
                    tracks_added += 1
                else:
                    # Track already in playlist or other failure
                    duplicates_skipped += 1
            else:
                # Track not in database
                unresolved_paths.append(track_path_str)

    return tracks_added, duplicates_skipped, unresolved_paths


def import_m3u(
    local_path: Path,
    playlist_name: str,
    library_root: Path,
    description: Optional[str] = None,
) -> tuple[int, int, int, list[str]]:
    """
    Import an M3U/M3U8 playlist file.

    Args:
        local_path: Path to the M3U/M3U8 file
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
    if not local_path.exists():
        raise FileNotFoundError(f"Playlist file not found: {local_path}")

    # Read M3U file
    try:
        # Try UTF-8 first (M3U8 standard)
        with open(local_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except UnicodeDecodeError:
        # Fall back to latin-1 for older M3U files
        with open(local_path, "r", encoding="latin-1") as f:
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
        if not line or line.startswith("#EXTM3U"):
            continue
        if line.startswith("#") and not line.startswith("#EXTINF"):
            continue
        if line.startswith("#EXTINF"):
            continue  # Metadata line, actual path comes next

        track_paths.append(line)

    # Create playlist
    playlist_id = create_playlist(
        name=playlist_name,
        playlist_type="manual",
        description=description or f"Imported from {local_path.name}",
    )

    # Resolve and add tracks using helper function
    tracks_added, duplicates_skipped, unresolved_paths = _add_tracks_from_paths(
        playlist_id=playlist_id,
        playlist_local_path=local_path,
        track_paths=track_paths,
        library_root=library_root,
    )

    return playlist_id, tracks_added, duplicates_skipped, unresolved_paths


def import_serato_crate(
    local_path: Path,
    playlist_name: str,
    library_root: Path,
    description: Optional[str] = None,
) -> tuple[int, int, int, list[str]]:
    """
    Import a Serato .crate playlist file.

    Args:
        local_path: Path to the .crate file
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
    if not local_path.exists():
        raise FileNotFoundError(f"Crate file not found: {local_path}")

    try:
        from pyserato.builder import Builder
    except ImportError:
        raise ImportError(
            "pyserato library not installed. Install with: uv pip install pyserato"
        )

    # Parse Serato crate
    try:
        builder = Builder()
        crate = builder.parse_crate(str(local_path))
    except Exception as e:
        raise ValueError(f"Failed to parse Serato crate: {e}")

    # Extract track paths from crate
    # Serato crates store tracks with full paths
    # Note: pyserato object structure may vary by version
    track_paths = []
    try:
        if hasattr(crate, "tracks"):
            for track in crate.tracks:
                if hasattr(track, "path"):
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
        playlist_type="manual",
        description=description or f"Imported from {local_path.name}",
    )

    # Resolve and add tracks using helper function
    tracks_added, duplicates_skipped, unresolved_paths = _add_tracks_from_paths(
        playlist_id=playlist_id,
        playlist_local_path=local_path,
        track_paths=track_paths,
        library_root=library_root,
    )

    return playlist_id, tracks_added, duplicates_skipped, unresolved_paths


def validate_csv_metadata_field(
    field_name: str, value: str
) -> tuple[bool, Optional[str]]:
    """
    Validate a CSV metadata field value.

    Args:
        field_name: Name of the metadata field
        value: String value from CSV

    Returns:
        Tuple of (is_valid, error_message_or_none)
    """
    if not value.strip():  # Empty values are OK (will be None in DB)
        return True, None

    # Field-specific validation
    if field_name in ["year"]:
        try:
            int(value)
        except ValueError:
            return False, f"Year must be a valid integer, got '{value}'"
    elif field_name in ["duration", "bpm"]:
        try:
            float(value)
        except ValueError:
            return False, f"{field_name.title()} must be a valid number, got '{value}'"

    return True, None


def import_csv(
    local_path: Path,
    playlist_name: str,
    description: Optional[str] = None,
) -> tuple[int, int, int, list[str]]:
    """
    Import a CSV playlist file with track metadata.

    Expected CSV format:
    - Must have headers (first row)
    - At minimum, should have 'local_path' column
    - Other columns match track metadata fields
    - Tracks are matched by local_path for updates, or created if not found

    Args:
        local_path: Path to the CSV file
        playlist_name: Name for the imported playlist
        description: Optional description for the playlist

    Returns:
        Tuple of (playlist_id, tracks_added, duplicates_skipped, error_messages)
        - playlist_id: ID of created playlist
        - tracks_added: Number of tracks successfully added
        - duplicates_skipped: Number of duplicate tracks skipped
        - error_messages: List of validation/parsing error messages

    Raises:
        FileNotFoundError: If CSV file doesn't exist
        ValueError: If CSV format is invalid
    """
    if not local_path.exists():
        raise FileNotFoundError(f"CSV file not found: {local_path}")

    # Read and parse CSV
    try:
        with open(local_path, "r", encoding="utf-8") as csvfile:
            # Try to detect if file has headers by reading first few lines
            sample = csvfile.read(1024)
            csvfile.seek(0)

            # Use csv.Sniffer to detect CSV dialect
            try:
                sniffer = csv.Sniffer()
                dialect = sniffer.sniff(sample, delimiters=",\t;|")
                has_header = sniffer.has_header(sample)
            except csv.Error:
                # Fall back to basic comma-separated with header assumption
                dialect = csv.excel()
                has_header = True

            if not has_header:
                raise ValueError(
                    "CSV file must have headers in the first row. "
                    "Expected columns include: local_path, title, artist, album, etc."
                )

            reader = csv.DictReader(csvfile, dialect=dialect)

            # Validate headers
            if not reader.fieldnames:
                raise ValueError("CSV file appears to be empty or malformed")

            required_fields = ["local_path"]
            missing_required = [
                field for field in required_fields if field not in reader.fieldnames
            ]
            if missing_required:
                raise ValueError(
                    f"CSV missing required columns: {', '.join(missing_required)}"
                )

            # Valid metadata fields from database schema
            valid_metadata_fields = {
                "title",
                "artist",
                "top_level_artist",
                "album",
                "genre",
                "year",
                "duration",
                "key_signature",
                "bpm",
                "remix_artist",
                "soundcloud_id",
                "spotify_id",
                "youtube_id",
                "source",
            }

            # Parse rows
            tracks_data = []
            error_messages = []

            for row_num, row in enumerate(
                reader, start=2
            ):  # Start at 2 since row 1 is header
                local_path_str = row.get("local_path", "").strip()
                if not local_path_str:
                    error_messages.append(f"Row {row_num}: Missing local_path")
                    continue

                # Validate local_path exists as file
                track_path = Path(local_path_str).expanduser()
                if not track_path.exists():
                    error_messages.append(
                        f"Row {row_num}: Track file not found: {local_path_str}"
                    )
                    continue

                # Validate metadata fields
                track_metadata: dict[str, Any] = {"local_path": str(track_path)}

                for field_name, value in row.items():
                    if field_name == "local_path":
                        continue  # Already handled

                    if field_name not in valid_metadata_fields:
                        # Skip unknown fields silently
                        continue

                    value = value.strip() if value else ""
                    if value:  # Only validate non-empty values
                        is_valid, error_msg = validate_csv_metadata_field(
                            field_name, value
                        )
                        if not is_valid:
                            error_messages.append(
                                f"Row {row_num}, {field_name}: {error_msg}"
                            )
                            continue

                        # Convert types appropriately
                        if field_name == "year":
                            track_metadata[field_name] = (
                                value  # Will be converted to int in DB
                            )
                        elif field_name in ["duration", "bpm"]:
                            track_metadata[field_name] = (
                                value  # Will be converted to float in DB
                            )
                        else:
                            track_metadata[field_name] = value

                tracks_data.append(track_metadata)

    except UnicodeDecodeError:
        raise ValueError(
            f"CSV file encoding error. File must be UTF-8 encoded: {local_path}"
        )
    except csv.Error as e:
        raise ValueError(f"CSV parsing error: {e}")

    # Create playlist
    playlist_id = create_playlist(
        name=playlist_name,
        playlist_type="manual",
        description=description or f"Imported from {local_path.name}",
    )

    # Process tracks: update/create in database and add to playlist
    tracks_added = 0
    duplicates_skipped = 0

    with get_db_connection() as conn:
        cursor = conn.cursor()

        for track_data in tracks_data:
            local_path_str = track_data["local_path"]

            # Check if track exists in database
            cursor.execute(
                "SELECT id FROM tracks WHERE local_path = ?", (local_path_str,)
            )
            existing_track = cursor.fetchone()

            if existing_track:
                # Update existing track metadata
                track_id = existing_track["id"]

                # Build update query dynamically
                update_fields = []
                update_values = []
                for field, value in track_data.items():
                    if field != "local_path":  # Don't update local_path
                        update_fields.append(f"{field} = ?")
                        update_values.append(value)

                if update_fields:
                    update_query = f"""
                        UPDATE tracks
                        SET {", ".join(update_fields)}, metadata_updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """
                    update_values.append(track_id)
                    cursor.execute(update_query, update_values)
            else:
                # Create new track
                # Build insert query dynamically
                fields = list(track_data.keys())
                placeholders = ["?" for _ in fields]
                values = list(track_data.values())

                insert_query = f"""
                    INSERT INTO tracks ({", ".join(fields)}, metadata_updated_at)
                    VALUES ({", ".join(placeholders)}, CURRENT_TIMESTAMP)
                """
                cursor.execute(insert_query, values)
                track_id = cursor.lastrowid
                if track_id is None:
                    error_messages.append(
                        f"Failed to create track: {track_data.get('local_path', 'unknown')}"
                    )
                    continue

            # Add track to playlist
            if add_track_to_playlist(playlist_id, cast(int, track_id)):
                tracks_added += 1
            else:
                duplicates_skipped += 1

    return playlist_id, tracks_added, duplicates_skipped, error_messages


def import_playlist(
    local_path: Path,
    playlist_name: Optional[str] = None,
    library_root: Optional[Path] = None,
    description: Optional[str] = None,
) -> tuple[int, int, int, list[str]]:
    """
    Import a playlist from a file, auto-detecting format.

    Args:
        local_path: Path to the playlist file
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
        playlist_name = local_path.stem

    # Default library root to ~/Music
    if library_root is None:
        library_root = Path.home() / "Music"

    # Detect format
    format_type = detect_playlist_format(local_path)

    if format_type == "m3u8":
        return import_m3u(local_path, playlist_name, library_root, description)
    elif format_type == "crate":
        return import_serato_crate(local_path, playlist_name, library_root, description)
    elif format_type == "csv":
        return import_csv(local_path, playlist_name, description)
    else:
        raise ValueError(
            f"Unsupported playlist format: {local_path.suffix}. "
            "Supported formats: .m3u, .m3u8, .crate, .csv"
        )
