"""
Playlist export functionality for Music Minion CLI.
Supports exporting to M3U/M3U8 and Serato .crate formats.
"""

import csv
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from music_minion.domain.library.metadata import write_elo_to_file

from .crud import get_playlist_by_id, get_playlist_by_name, get_playlist_tracks


def make_relative_path(track_path: Path, library_root: Path) -> str:
    """
    Convert an absolute track path to a relative path from library root.

    Args:
        track_path: Absolute path to the track file
        library_root: Root directory of music library

    Returns:
        Relative path string from library root
    """
    try:
        # Try to make path relative to library root
        rel_path = track_path.relative_to(library_root)
        return str(rel_path)
    except ValueError:
        # track_path is not relative to library_root
        # Return absolute path as fallback
        return str(track_path)


def export_m3u8(
    playlist_id: int,
    output_path: Path,
    library_root: Path,
    use_relative_paths: bool = True,
) -> int:
    """
    Export a playlist to M3U8 format (UTF-8 encoded M3U).

    Args:
        playlist_id: ID of the playlist to export
        output_path: Path where M3U8 file should be written
        library_root: Root directory of music library (for relative paths)
        use_relative_paths: Whether to use relative paths (default True)

    Returns:
        Number of tracks exported

    Raises:
        ValueError: If playlist doesn't exist or is empty
    """
    # Get playlist info
    pl = get_playlist_by_id(playlist_id)
    if not pl:
        raise ValueError(f"Playlist with ID {playlist_id} not found")

    # Get tracks
    tracks = get_playlist_tracks(playlist_id)
    if not tracks:
        raise ValueError(f"Playlist '{pl['name']}' is empty")

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write M3U8 file
    with open(output_path, "w", encoding="utf-8") as f:
        # Write header
        f.write("#EXTM3U\n")
        f.write(f"# Playlist: {pl['name']}\n")
        if pl.get("description"):
            f.write(f"# Description: {pl['description']}\n")
        f.write(f"# Exported: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"# Tracks: {len(tracks)}\n")
        f.write("\n")

        # Write tracks
        for track in tracks:
            track_path = Path(track["local_path"])

            # Write EXTINF line (metadata)
            duration = int(track.get("duration") or 0)
            artist = track.get("artist", "Unknown Artist")
            title = track.get("title", track_path.stem)
            f.write(f"#EXTINF:{duration},{artist} - {title}\n")

            # Write file path
            if use_relative_paths:
                path_str = make_relative_path(track_path, library_root)
            else:
                path_str = str(track_path)

            f.write(f"{path_str}\n")

    return len(tracks)


def export_serato_crate(
    playlist_id: int, output_path: Path, library_root: Path, syncthing_config=None
) -> int:
    """
    Export a playlist to Serato .crate format.

    Note: Serato crates are stored in a _Serato_/SubCrates/ directory structure.
    This function creates the proper Serato directory structure and exports the crate.

    Args:
        playlist_id: ID of the playlist to export
        output_path: Directory where _Serato_ folder structure will be created
        library_root: Root directory of music library

    Returns:
        Number of tracks exported

    Raises:
        ValueError: If playlist doesn't exist or is empty
        ImportError: If pyserato is not installed
    """
    try:
        from pyserato.builder import Builder
        from pyserato.model.crate import Crate
        from pyserato.model.track import Track
    except ImportError:
        raise ImportError(
            "pyserato library not installed. Install with: uv pip install pyserato"
        )

    # Get playlist info
    pl = get_playlist_by_id(playlist_id)
    if not pl:
        raise ValueError(f"Playlist with ID {playlist_id} not found")

    # Get tracks
    tracks = get_playlist_tracks(playlist_id)
    if not tracks:
        raise ValueError(f"Playlist '{pl['name']}' is empty")

    # Create Serato directory structure
    # pyserato expects a _Serato_ directory and will create SubCrates/ inside it
    serato_dir = output_path / "_Serato_"
    serato_dir.mkdir(parents=True, exist_ok=True)

    # Create Serato crate
    crate = Crate(pl["name"])

    # Add tracks to crate
    added_count = 0
    failed_count = 0
    for track in tracks:
        try:
            track_path = Path(track["local_path"]).absolute()

            # Translate path to Windows format if Syncthing is enabled
            if syncthing_config and syncthing_config.enabled:
                # Translate to Windows path string (without drive letter)
                path_str = syncthing_config.translate_to_windows(str(track_path))
                # Pass as string - our monkey-patched resolve() will preserve it
                serato_track = Track(path=path_str)
            else:
                # Use Path object for Linux paths
                serato_track = Track(path=track_path)

            crate.add_track(serato_track)
            added_count += 1
        except Exception as e:
            # Log errors but continue processing
            failed_count += 1
            if failed_count <= 5:  # Only log first 5 failures
                from loguru import logger
                logger.warning(f"Failed to add track to crate: {track.get('local_path', 'unknown')} - {e}")

    if failed_count > 0:
        from loguru import logger
        logger.warning(f"Crate export: {added_count} tracks added, {failed_count} tracks failed")

    # Save crate using pyserato builder
    # Builder.save() will create SubCrates/<crate_name>.crate inside the _Serato_ directory
    #
    # IMPORTANT: pyserato calls Path(track.path).resolve() which treats Windows paths
    # as relative on Linux. Monkey-patch PosixPath.resolve() to preserve Windows paths.
    if syncthing_config and syncthing_config.enabled:
        from pathlib import PosixPath

        original_resolve = PosixPath.resolve

        def patched_resolve(self, strict=False):
            path_str = str(self)
            # Detect Windows-style path (with or without drive letter)
            is_windows = (
                (len(path_str) >= 3 and path_str[1:3] == ":/")
                or path_str.startswith("Users/")
                or path_str.startswith("Program Files/")
            )
            if is_windows:
                # Return self unchanged - don't resolve Windows paths on Linux
                return self
            return original_resolve(self, strict=strict)

        PosixPath.resolve = patched_resolve

    try:
        builder = Builder()
        builder.save(crate, serato_dir, overwrite=True)
    finally:
        if syncthing_config and syncthing_config.enabled:
            PosixPath.resolve = original_resolve

    return len(tracks)


def export_csv(
    playlist_id: int,
    output_path: Path,
) -> int:
    """
    Export a playlist to CSV format with all track metadata including database ID.

    Note: NULL values are exported as empty strings for CSV compatibility.

    Args:
        playlist_id: ID of the playlist to export
        output_path: Path where CSV file should be written

    Returns:
        Number of tracks exported

    Raises:
        ValueError: If playlist doesn't exist or is empty
    """
    # Get playlist info
    pl = get_playlist_by_id(playlist_id)
    if not pl:
        raise ValueError(f"Playlist with ID {playlist_id} not found")

    # Get tracks
    tracks = get_playlist_tracks(playlist_id)
    if not tracks:
        raise ValueError(f"Playlist '{pl['name']}' is empty")

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Define CSV field names (all available track metadata)
    fieldnames = [
        "id",  # Database ID
        "position",  # Position in playlist
        "playlist_elo_rating",
        "title",
        "artist",
        "top_level_artist",
        "remix_artist",
        "genre",
        "year",
        "duration",
        "key_signature",
        "bpm",
        "album",
        "local_path",
        "soundcloud_id",
        "spotify_id",
        "youtube_id",
        "source",
        # ELO Ratings
        "playlist_elo_comparison_count",
        "playlist_elo_wins",
        "global_elo_rating",
        "global_elo_comparison_count",
        "global_elo_wins",
    ]

    # Write CSV file
    with open(output_path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        writer.writeheader()

        for track in tracks:
            # Convert track dict to CSV row, ensuring all fields are present
            row = {}
            for field in fieldnames:
                value = track.get(field)
                # Convert None to empty string for CSV
                if value is None:
                    row[field] = ""
                elif field in ["playlist_elo_rating", "global_elo_rating"]:
                    # Round ELO ratings to 0 decimal places
                    row[field] = str(int(round(float(value))))
                else:
                    row[field] = str(value)
            writer.writerow(row)

    return len(tracks)


def export_playlist(
    playlist_id: Optional[int] = None,
    playlist_name: Optional[str] = None,
    format_type: str = "m3u8",
    output_path: Optional[Path] = None,
    library_root: Optional[Path] = None,
    use_relative_paths: bool = True,
    sync_metadata: bool = False,
    syncthing_config=None,
) -> tuple[Path, int]:
    """
    Export a playlist to a file, with flexible format selection.

    Args:
        playlist_id: ID of the playlist to export (provide either this or playlist_name)
        playlist_name: Name of the playlist to export
        format_type: Export format ('m3u8', 'crate', 'csv') - default 'm3u8'
        output_path: Where to save the file (defaults to ~/Music/playlists/<name>.<ext>)
        library_root: Root directory of music library (defaults to ~/Music)
        use_relative_paths: Whether to use relative paths for M3U8 (default True)
        sync_metadata: Whether to sync PLAYLIST_ELO to COMMENT field in audio files

    Returns:
        Tuple of (output_path, tracks_exported)

    Raises:
        ValueError: If playlist not found or format unsupported
    """
    # Get playlist info
    if playlist_id:
        pl = get_playlist_by_id(playlist_id)
    elif playlist_name:
        pl = get_playlist_by_name(playlist_name)
    else:
        raise ValueError("Must provide either playlist_id or playlist_name")

    if not pl:
        raise ValueError("Playlist not found")

    # Default library root to ~/Music and ensure it's a Path object
    if library_root is None:
        library_root = Path.home() / "Music"
    else:
        # Ensure library_root is a Path (no-op if already Path, converts if string)
        library_root = Path(library_root)

    # Default output path based on format
    if output_path is None:
        if format_type == "crate":
            # Crate format: export to library_root/_Serato_/SubCrates (standard Serato location)
            output_path = library_root
        else:
            # Other formats: export to library_root/playlists
            playlists_dir = library_root / "playlists"
            playlists_dir.mkdir(parents=True, exist_ok=True)

            if format_type == "m3u8":
                output_path = playlists_dir / f"{pl['name']}.m3u8"
            elif format_type == "csv":
                output_path = playlists_dir / f"{pl['name']}.csv"
            else:
                raise ValueError(
                    f"Unsupported format: {format_type}. Use 'm3u8', 'crate', or 'csv'"
                )

    # Export based on format
    if format_type == "m3u8":
        tracks_exported = export_m3u8(
            playlist_id=pl["id"],
            output_path=output_path,
            library_root=library_root,
            use_relative_paths=use_relative_paths,
        )
    elif format_type == "crate":
        tracks_exported = export_serato_crate(
            playlist_id=pl["id"],
            output_path=output_path,
            library_root=library_root,
            syncthing_config=syncthing_config,
        )
        # Update output_path to reflect the actual .crate file location
        output_path = output_path / "_Serato_" / "SubCrates" / f"{pl['name']}.crate"
    elif format_type == "csv":
        tracks_exported = export_csv(playlist_id=pl["id"], output_path=output_path)
    else:
        raise ValueError(
            f"Unsupported format: {format_type}. Use 'm3u8', 'crate', or 'csv'"
        )

    # Sync ELO metadata to files if requested
    if sync_metadata:
        from loguru import logger

        tracks = get_playlist_tracks(pl["id"])
        elo_success = 0
        elo_failed = 0

        for track in tracks:
            local_path = track.get("local_path")
            playlist_elo = track.get("playlist_elo_rating")

            # Skip tracks without local files or ELO ratings
            if not local_path or not os.path.exists(local_path):
                continue
            if playlist_elo is None or playlist_elo == 1500.0:
                continue

            success = write_elo_to_file(
                local_path=local_path,
                playlist_elo=playlist_elo,
                update_comment=True,  # Prepend to COMMENT for DJ software sorting
            )

            if success:
                elo_success += 1
            else:
                elo_failed += 1

        if elo_success > 0 or elo_failed > 0:
            logger.info(
                f"ELO metadata sync: {elo_success} succeeded, {elo_failed} failed"
            )

    return output_path, tracks_exported


def auto_export_playlist(
    playlist_id: int,
    export_formats: list[str],
    library_root: Path,
    use_relative_paths: bool = True,
    sync_metadata: bool = False,
    syncthing_config=None,
) -> list[tuple[str, Path, int]]:
    """
    Auto-export a playlist to multiple formats.

    Used internally when playlists are modified and auto-export is enabled.

    Args:
        playlist_id: ID of the playlist to export
        export_formats: List of formats to export ('m3u8', 'crate', 'csv')
        library_root: Root directory of music library
        use_relative_paths: Whether to use relative paths for M3U8
        sync_metadata: Whether to sync PLAYLIST_ELO to COMMENT field in audio files
        syncthing_config: Syncthing configuration for path translation

    Returns:
        List of tuples (format, output_path, tracks_exported)
    """
    results = []

    for format_type in export_formats:
        try:
            output_path, tracks_exported = export_playlist(
                playlist_id=playlist_id,
                format_type=format_type,
                library_root=library_root,
                use_relative_paths=use_relative_paths,
                sync_metadata=sync_metadata,
                syncthing_config=syncthing_config,
            )
            results.append((format_type, output_path, tracks_exported))
        except (ValueError, FileNotFoundError, ImportError, OSError) as e:
            # Expected errors during export - fail silently for auto-export
            # Write to stderr for debugging without interrupting user workflow
            print(f"Auto-export failed for format {format_type}: {e}", file=sys.stderr)
        except Exception as e:
            # Unexpected errors - log for debugging
            print(
                f"Unexpected error during auto-export ({format_type}): {e}",
                file=sys.stderr,
            )

    return results


def export_all_playlists(
    export_formats: list[str], library_root: Path, use_relative_paths: bool = True
) -> dict[str, list[tuple[str, Path, int]]]:
    """
    Export all playlists to specified formats.

    Args:
        export_formats: List of formats to export ('m3u8', 'crate', 'csv')
        library_root: Root directory of music library
        use_relative_paths: Whether to use relative paths for M3U8

    Returns:
        Dict mapping playlist names to list of (format, output_path, tracks_exported)
    """
    from .crud import get_all_playlists

    all_playlists = get_all_playlists()
    results = {}

    for pl in all_playlists:
        playlist_results = auto_export_playlist(
            playlist_id=pl["id"],
            export_formats=export_formats,
            library_root=library_root,
            use_relative_paths=use_relative_paths,
        )
        if playlist_results:
            results[pl["name"]] = playlist_results

    return results
