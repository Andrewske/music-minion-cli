"""
Playlist import functionality for Music Minion CLI.
Supports importing M3U/M3U8 and Serato .crate playlists.
"""

import csv
import urllib.parse
from pathlib import Path
from typing import Optional, cast

from music_minion.core import database
from music_minion.core.database import get_db_connection

from .crud import add_track_to_playlist, create_playlist

# CSV import security limits
MAX_CSV_SIZE = 10 * 1024 * 1024  # 10MB
MAX_CSV_ROWS = 10000
MAX_FIELD_LENGTH = 1000

# Valid metadata fields for CSV import
VALID_CSV_METADATA_FIELDS = {
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
    - Cross-platform paths (Mac/Windows -> Linux)

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

    track_path_obj = Path(track_path)

    # If already absolute and exists, return it
    if track_path_obj.is_absolute() and track_path_obj.exists():
        return track_path_obj

    # Try to extract relative part after known music directory markers
    # This handles cross-platform paths (Mac -> Linux, Windows -> Linux)
    # e.g., "Users/kevin/Music/EDM/track.mp3" → "EDM/track.mp3"
    parts = track_path_obj.parts
    for i, part in enumerate(parts):
        if part.lower() in ["music", "music library", "itunes", "serato"]:
            rel_parts = parts[i + 1 :]
            if rel_parts:
                candidate = library_root / Path(*rel_parts)
                if candidate.exists():
                    return candidate
            break  # Only try first match

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
        from serato_crate import SeratoCrate
    except ImportError:
        raise ImportError(
            "serato-crate library not installed. Install with: uv pip install serato-crate"
        )

    # Parse Serato crate using class method .load()
    try:
        crate = SeratoCrate.load(local_path)
    except Exception as e:
        raise ValueError(f"Failed to parse Serato crate: {e}")

    # Extract track paths from crate
    # SeratoCrate.tracks is a list of Path objects (relative to drive root)
    track_paths = []
    try:
        for track_path in crate.tracks:
            # Convert Path object to string
            track_paths.append(str(track_path))

        # If no tracks found, the crate is empty
        if not track_paths:
            raise ValueError(
                "Serato crate is empty (contains no tracks)."
            )
    except AttributeError as e:
        raise ValueError(
            f"Failed to extract tracks from Serato crate (API mismatch?): {e}"
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


def _parse_csv_file(local_path: Path) -> tuple[csv.DictReader, dict]:
    """Handle CSV file reading and dialect detection."""
    csvfile = open(local_path, "r", encoding="utf-8")
    sample = csvfile.read(1024)
    csvfile.seek(0)

    try:
        sniffer = csv.Sniffer()
        dialect = sniffer.sniff(sample, delimiters=",\t;|")
        has_header = sniffer.has_header(sample)
    except csv.Error:
        dialect = csv.excel()
        has_header = True

    if not has_header:
        raise ValueError("CSV file must have headers in the first row")

    reader = csv.DictReader(csvfile, dialect=dialect)

    if "local_path" not in (reader.fieldnames or []):
        raise ValueError("CSV missing required 'local_path' column")

    return reader, {"valid_fields": VALID_CSV_METADATA_FIELDS}


def _validate_csv_rows(
    reader: csv.DictReader, library_root: Path, valid_fields: set[str]
) -> tuple[list[dict], list[str]]:
    """Parse and validate CSV rows with security checks."""
    tracks_data = []
    error_messages = []

    for row_num, row in enumerate(reader, start=2):
        local_path_str = row.get("local_path", "").strip()
        if not local_path_str:
            error_messages.append(f"Row {row_num}: Missing local_path")
            continue

        track_path = Path(local_path_str).expanduser()
        if not track_path.exists():
            error_messages.append(
                f"Row {row_num}: Track file not found: {local_path_str}"
            )
            continue

        try:
            track_path.resolve().relative_to(library_root.resolve())
        except ValueError:
            error_messages.append(
                f"Row {row_num}: Track outside library root: {local_path_str}"
            )
            continue

        track_metadata = {
            "local_path": str(track_path),
            "source": "csv"  # Track ownership for data loss prevention
        }

        for field_name, value in row.items():
            if (
                field_name != "local_path"
                and field_name in valid_fields
                and (value := value.strip())
            ):
                is_valid, error_msg = validate_csv_metadata_field(field_name, value)
                if is_valid:
                    track_metadata[field_name] = value
                else:
                    error_messages.append(f"Row {row_num}, {field_name}: {error_msg}")

        tracks_data.append(track_metadata)

    return tracks_data, error_messages


def _upsert_tracks_to_playlist(
    playlist_id: int, tracks_data: list[dict]
) -> tuple[int, int]:
    """
    Database operations in single transaction.

    Args:
        playlist_id: ID of the playlist to add tracks to
        tracks_data: List of track metadata dictionaries

    Returns:
        Tuple of (tracks_added, duplicates_skipped)
    """
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
                    # This would be an error case, but we'll skip for now
                    continue

            # Add track to playlist
            if add_track_to_playlist(playlist_id, cast(int, track_id)):
                tracks_added += 1
            else:
                duplicates_skipped += 1

    return tracks_added, duplicates_skipped


def import_csv(
    local_path: Path,
    playlist_name: str,
    library_root: Path,
    description: Optional[str] = None,
) -> tuple[int, int, int, list[str]]:
    """
    Import a CSV playlist file with track metadata.

    Two-phase approach:
    1. Parse and validate entire CSV (collect all errors)
    2. Batch process all valid tracks in single transaction

    Args:
        local_path: Path to the CSV file
        playlist_name: Name for the imported playlist
        library_root: Root directory of music library (for path validation)
        description: Optional description for the playlist

    Returns:
        Tuple of (playlist_id, tracks_added, duplicates_skipped, error_messages)

    Raises:
        FileNotFoundError: If CSV file doesn't exist
        ValueError: If CSV format is invalid
    """
    if not local_path.exists():
        raise FileNotFoundError(f"CSV file not found: {local_path}")

    # Phase 1: Parse and validate
    reader, metadata = _parse_csv_file(local_path)

    valid_tracks_data, error_messages = _validate_csv_rows(
        reader, library_root, VALID_CSV_METADATA_FIELDS
    )

    # Create playlist
    playlist_id = create_playlist(
        name=playlist_name,
        playlist_type="manual",
        description=description or f"Imported from {local_path.name}",
    )

    # Phase 2: Batch process valid tracks
    if valid_tracks_data:
        tracks_added, duplicates_skipped = _upsert_tracks_to_playlist(
            playlist_id, valid_tracks_data
        )
    else:
        tracks_added, duplicates_skipped = 0, 0

    return playlist_id, tracks_added, duplicates_skipped, error_messages


def import_playlist_metadata_csv(
    local_path: Path,
) -> tuple[int, int, int, list[str]]:
    """
    Import track metadata from a CSV file and update existing tracks.

    Expected CSV format:
    - Must have headers (first row)
    - Must have an identifier column (local_path, id, or title+artist)
    - Other columns match track metadata fields
    - Tracks are matched by identifier and updated in database + files

    Args:
        local_path: Path to the CSV file

    Returns:
        Tuple of (tracks_updated, tracks_not_found, validation_errors, error_messages)
        - tracks_updated: Number of tracks successfully updated
        - tracks_not_found: Number of tracks that couldn't be found
        - validation_errors: Number of rows with validation errors
        - error_messages: List of error messages

    Raises:
        FileNotFoundError: If CSV file doesn't exist
        ValueError: If CSV format is invalid
    """
    if not local_path.exists():
        raise FileNotFoundError(f"CSV file not found: {local_path}")

    # Security check: file size limit
    file_size = local_path.stat().st_size
    if file_size > MAX_CSV_SIZE:
        raise ValueError(
            f"CSV file too large: {file_size / 1024 / 1024:.1f}MB "
            f"(max {MAX_CSV_SIZE / 1024 / 1024}MB)"
        )

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

            # Check for identifier columns
            identifier_columns = ["local_path", "id", "title", "artist"]
            available_identifiers = [
                col for col in identifier_columns if col in reader.fieldnames
            ]

            if not available_identifiers:
                raise ValueError(
                    f"CSV must have at least one identifier column: {', '.join(identifier_columns)}"
                )

            # Valid metadata fields from database schema
            valid_metadata_fields = {
                "title",
                "artist",
                "remix_artist",
                "album",
                "genre",
                "year",
                "bpm",
                "key_signature",
            }

            # Parse and validate rows
            update_operations = []
            error_messages = []
            validation_errors = 0

            for row_num, row in enumerate(
                reader, start=2
            ):  # Start at 2 since row 1 is header
                # Security check: row count limit
                if row_num > MAX_CSV_ROWS + 2:  # +2 for header row offset
                    error_messages.append(
                        f"CSV file too large: exceeded {MAX_CSV_ROWS} rows"
                    )
                    break

                # Extract identifier
                identifier = None
                identifier_type = None

                if "local_path" in row and row["local_path"].strip():
                    identifier = row["local_path"].strip()
                    identifier_type = "local_path"
                elif "id" in row and row["id"].strip():
                    try:
                        identifier = int(row["id"].strip())
                        identifier_type = "id"
                    except ValueError:
                        error_messages.append(
                            f"Row {row_num}: Invalid track ID '{row['id']}'"
                        )
                        validation_errors += 1
                        continue
                elif "title" in row and "artist" in row:
                    title = row["title"].strip()
                    artist = row["artist"].strip()
                    if title and artist:
                        identifier = {"title": title, "artist": artist}
                        identifier_type = "title_artist"
                    else:
                        error_messages.append(
                            f"Row {row_num}: Missing title or artist for identification"
                        )
                        validation_errors += 1
                        continue
                else:
                    error_messages.append(f"Row {row_num}: No valid identifier found")
                    validation_errors += 1
                    continue

                # Extract metadata fields to update
                metadata_updates = {}
                for field_name, value in row.items():
                    if field_name in [
                        "local_path",
                        "id",
                    ]:  # Skip identifier-only fields
                        continue  # But allow title/artist to be updated

                    if field_name not in valid_metadata_fields:
                        # Skip unknown fields silently
                        continue

                    value = value.strip() if value else ""
                    if value:  # Only validate non-empty values
                        # Security check: field length limit
                        if len(value) > MAX_FIELD_LENGTH:
                            error_messages.append(
                                f"Row {row_num}, {field_name}: "
                                f"Value too long ({len(value)} chars, max {MAX_FIELD_LENGTH})"
                            )
                            validation_errors += 1
                            continue

                        is_valid, error_msg = validate_csv_metadata_field(
                            field_name, value
                        )
                        if not is_valid:
                            error_messages.append(
                                f"Row {row_num}, {field_name}: {error_msg}"
                            )
                            validation_errors += 1
                            continue

                        # Convert types appropriately
                        if field_name == "year":
                            metadata_updates[field_name] = int(value)
                        elif field_name == "bpm":
                            metadata_updates[field_name] = int(
                                float(value)
                            )  # BPM stored as int
                        else:
                            metadata_updates[field_name] = value

                if metadata_updates:
                    update_operations.append(
                        {
                            "identifier": identifier,
                            "identifier_type": identifier_type,
                            "updates": metadata_updates,
                            "row_num": row_num,
                        }
                    )
                else:
                    error_messages.append(
                        f"Row {row_num}: No metadata fields to update"
                    )
                    validation_errors += 1

    except UnicodeDecodeError:
        raise ValueError(
            f"CSV file encoding error. File must be UTF-8 encoded: {local_path}"
        )
    except csv.Error as e:
        raise ValueError(f"CSV parsing error: {e}")

    # Process updates
    tracks_updated = 0
    tracks_not_found = 0

    for operation in update_operations:
        try:
            # Find track by identifier
            track_id = None

            if operation["identifier_type"] == "local_path":
                track_path = Path(operation["identifier"]).expanduser()
                track = database.get_track_by_path(str(track_path))
                if track:
                    track_id = track["id"]

            elif operation["identifier_type"] == "id":
                track = database.get_track_by_id(operation["identifier"])
                if track:
                    track_id = track["id"]

            elif operation["identifier_type"] == "title_artist":
                # Find by title and artist combination
                with database.get_db_connection() as conn:
                    cursor = conn.execute(
                        "SELECT id FROM tracks WHERE title = ? AND artist = ? LIMIT 1",
                        (
                            operation["identifier"]["title"],
                            operation["identifier"]["artist"],
                        ),
                    )
                    row = cursor.fetchone()
                    if row:
                        track_id = row["id"]

            if track_id is None:
                tracks_not_found += 1
                error_messages.append(
                    f"Row {operation['row_num']}: Track not found with identifier {operation['identifier']}"
                )
                continue

            # Get full track data for comparison
            track = database.get_track_by_id(track_id)
            if not track:
                error_messages.append(
                    f"Row {operation['row_num']}: Could not retrieve track data for ID {track_id}"
                )
                continue

            # Filter updates to only include actual changes (not just format conversions)
            actual_updates = {}
            for field_name, new_value in operation["updates"].items():
                current_value = track.get(field_name)

                # Normalize both values for comparison
                if field_name == "bpm":
                    # Normalize BPM: convert floats to ints for comparison
                    if isinstance(current_value, float):
                        current_value = int(current_value)
                    if isinstance(new_value, float):
                        new_value = int(new_value)

                # Only include if actually different
                if new_value != current_value:
                    actual_updates[field_name] = new_value

            # Only update if there are actual changes
            if actual_updates:
                success = database.update_track_metadata(track_id, **actual_updates)
                if success:
                    tracks_updated += 1
                else:
                    error_messages.append(
                        f"Row {operation['row_num']}: Failed to update track metadata"
                    )
            # If no actual updates, this operation is silently skipped (no error)

        except Exception as e:
            error_messages.append(
                f"Row {operation['row_num']}: Error updating track: {e}"
            )

    return tracks_updated, tracks_not_found, validation_errors, error_messages


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
        return import_csv(local_path, playlist_name, library_root, description)
    else:
        raise ValueError(
            f"Unsupported playlist format: {local_path.suffix}. "
            "Supported formats: .m3u, .m3u8, .crate, .csv"
        )
