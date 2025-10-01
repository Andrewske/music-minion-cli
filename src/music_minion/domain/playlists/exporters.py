"""
Playlist export functionality for Music Minion CLI.
Supports exporting to M3U/M3U8 and Serato .crate formats.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import sys

from ...core.database import get_db_connection
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
    use_relative_paths: bool = True
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
    with open(output_path, 'w', encoding='utf-8') as f:
        # Write header
        f.write("#EXTM3U\n")
        f.write(f"# Playlist: {pl['name']}\n")
        if pl.get('description'):
            f.write(f"# Description: {pl['description']}\n")
        f.write(f"# Exported: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"# Tracks: {len(tracks)}\n")
        f.write("\n")

        # Write tracks
        for track in tracks:
            track_path = Path(track['file_path'])

            # Write EXTINF line (metadata)
            duration = int(track.get('duration', 0))
            artist = track.get('artist', 'Unknown Artist')
            title = track.get('title', track_path.stem)
            f.write(f"#EXTINF:{duration},{artist} - {title}\n")

            # Write file path
            if use_relative_paths:
                path_str = make_relative_path(track_path, library_root)
            else:
                path_str = str(track_path)

            f.write(f"{path_str}\n")

    return len(tracks)


def export_serato_crate(
    playlist_id: int,
    output_path: Path,
    library_root: Path
) -> int:
    """
    Export a playlist to Serato .crate format.

    Args:
        playlist_id: ID of the playlist to export
        output_path: Path where .crate file should be written
        library_root: Root directory of music library

    Returns:
        Number of tracks exported

    Raises:
        ValueError: If playlist doesn't exist or is empty
        ImportError: If pyserato is not installed
    """
    try:
        from pyserato.model.crate import Crate
        from pyserato.builder import Builder
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

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Create Serato crate
    crate = Crate(pl['name'])

    # Add tracks to crate
    for track in tracks:
        track_path = Path(track['file_path'])
        # Serato expects absolute paths
        crate.add_track(str(track_path.absolute()))

    # Save crate using pyserato builder
    builder = Builder()
    builder.save(crate, str(output_path))

    return len(tracks)


def export_playlist(
    playlist_id: Optional[int] = None,
    playlist_name: Optional[str] = None,
    format_type: str = 'm3u8',
    output_path: Optional[Path] = None,
    library_root: Optional[Path] = None,
    use_relative_paths: bool = True
) -> tuple[Path, int]:
    """
    Export a playlist to a file, with flexible format selection.

    Args:
        playlist_id: ID of the playlist to export (provide either this or playlist_name)
        playlist_name: Name of the playlist to export
        format_type: Export format ('m3u8', 'crate') - default 'm3u8'
        output_path: Where to save the file (defaults to ~/Music/playlists/<name>.<ext>)
        library_root: Root directory of music library (defaults to ~/Music)
        use_relative_paths: Whether to use relative paths for M3U8 (default True)

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

    # Default library root to ~/Music
    if library_root is None:
        library_root = Path.home() / "Music"

    # Default output path based on format
    if output_path is None:
        playlists_dir = library_root / "playlists"
        playlists_dir.mkdir(parents=True, exist_ok=True)

        if format_type == 'm3u8':
            output_path = playlists_dir / f"{pl['name']}.m3u8"
        elif format_type == 'crate':
            output_path = playlists_dir / f"{pl['name']}.crate"
        else:
            raise ValueError(f"Unsupported format: {format_type}. Use 'm3u8' or 'crate'")

    # Export based on format
    if format_type == 'm3u8':
        tracks_exported = export_m3u8(
            playlist_id=pl['id'],
            output_path=output_path,
            library_root=library_root,
            use_relative_paths=use_relative_paths
        )
    elif format_type == 'crate':
        tracks_exported = export_serato_crate(
            playlist_id=pl['id'],
            output_path=output_path,
            library_root=library_root
        )
    else:
        raise ValueError(f"Unsupported format: {format_type}. Use 'm3u8' or 'crate'")

    return output_path, tracks_exported


def auto_export_playlist(
    playlist_id: int,
    export_formats: List[str],
    library_root: Path,
    use_relative_paths: bool = True
) -> List[tuple[str, Path, int]]:
    """
    Auto-export a playlist to multiple formats.

    Used internally when playlists are modified and auto-export is enabled.

    Args:
        playlist_id: ID of the playlist to export
        export_formats: List of formats to export ('m3u8', 'crate')
        library_root: Root directory of music library
        use_relative_paths: Whether to use relative paths for M3U8

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
                use_relative_paths=use_relative_paths
            )
            results.append((format_type, output_path, tracks_exported))
        except (ValueError, FileNotFoundError, ImportError, OSError) as e:
            # Expected errors during export - fail silently for auto-export
            # Write to stderr for debugging without interrupting user workflow
            print(f"Auto-export failed for format {format_type}: {e}", file=sys.stderr)
        except Exception as e:
            # Unexpected errors - log for debugging
            print(f"Unexpected error during auto-export ({format_type}): {e}", file=sys.stderr)

    return results


def export_all_playlists(
    export_formats: List[str],
    library_root: Path,
    use_relative_paths: bool = True
) -> Dict[str, List[tuple[str, Path, int]]]:
    """
    Export all playlists to specified formats.

    Args:
        export_formats: List of formats to export ('m3u8', 'crate')
        library_root: Root directory of music library
        use_relative_paths: Whether to use relative paths for M3U8

    Returns:
        Dict mapping playlist names to list of (format, output_path, tracks_exported)
    """
    from .playlist import get_all_playlists

    all_playlists = get_all_playlists()
    results = {}

    for pl in all_playlists:
        playlist_results = auto_export_playlist(
            playlist_id=pl['id'],
            export_formats=export_formats,
            library_root=library_root,
            use_relative_paths=use_relative_paths
        )
        if playlist_results:
            results[pl['name']] = playlist_results

    return results