"""
Core utilities for Music Minion CLI.

Shared functions for command parsing, validation, and utilities.
"""

import sys
from pathlib import Path
from typing import List, Optional

from .core import config
from .core import database
from .domain import library
from .domain import playback
from .domain.playlists import exporters as playlist_export


# Rich Console instance (imported from main)
def get_console():
    """Get Rich Console instance from main module."""
    from . import main
    return main.console


def safe_print(message: str, style: str = None) -> None:
    """Print using Rich Console if available, otherwise fallback to regular print."""
    console = get_console()
    if console:
        if style:
            console.print(message, style=style)
        else:
            console.print(message)
    else:
        print(message)


def parse_quoted_args(args: List[str]) -> List[str]:
    """
    Parse command arguments respecting quoted strings.
    Handles both single and double quotes.

    Args:
        args: Raw argument list from command split

    Returns:
        List of parsed arguments with quotes removed

    Example:
        ['playlist', 'rename', '"Old', 'Name"', '"New', 'Name"']
        -> ['playlist', 'rename', 'Old Name', 'New Name']
    """
    parsed = []
    current = []
    in_quote = False
    quote_char = None

    for arg in args:
        # Check if this arg starts a quote
        if not in_quote and arg and arg[0] in ('"', "'"):
            quote_char = arg[0]
            in_quote = True
            # Check if quote also ends in same arg
            if len(arg) > 1 and arg[-1] == quote_char:
                parsed.append(arg[1:-1])
                in_quote = False
                quote_char = None
            else:
                current.append(arg[1:])
        # Check if this arg ends the current quote
        elif in_quote and arg and arg[-1] == quote_char:
            current.append(arg[:-1])
            parsed.append(' '.join(current))
            current = []
            in_quote = False
            quote_char = None
        # Inside a quote
        elif in_quote:
            current.append(arg)
        # Regular arg outside quotes
        else:
            parsed.append(arg)

    # If we have unclosed quotes, join what we have
    if current:
        parsed.append(' '.join(current))

    return parsed


def parse_command(user_input: str) -> tuple[str, List[str]]:
    """Parse user input into command and arguments."""
    parts = user_input.strip().split()
    if not parts:
        return "", []

    command = parts[0].lower()
    args = parts[1:] if len(parts) > 1 else []
    return command, args


def ensure_mpv_available() -> bool:
    """Check if MPV is available and warn if not."""
    if not playback.check_mpv_available():
        print("Error: MPV is not installed or not available in PATH.")
        print("Please install MPV to use playback features.")
        print("On Ubuntu/Debian: sudo apt install mpv")
        print("On Arch Linux: sudo pacman -S mpv")
        print("On macOS: brew install mpv")
        print("On Windows: Download from https://mpv.io/installation/ or use 'winget install mpv'")
        return False
    return True


def ensure_library_loaded() -> bool:
    """Ensure music library is loaded."""
    from . import main

    if not main.music_tracks:
        safe_print("Loading music library...", "blue")
        main.current_config = config.load_config()

        # Try to load from database first (much faster)
        db_tracks = database.get_all_tracks()
        if db_tracks:
            # Convert database tracks to library Track objects
            main.music_tracks = [database.db_track_to_library_track(track) for track in db_tracks]
            # Filter out files that no longer exist
            existing_tracks = []
            for track in main.music_tracks:
                if Path(track.file_path).exists():
                    existing_tracks.append(track)
            main.music_tracks = existing_tracks
            safe_print(f"Loaded {len(main.music_tracks)} tracks from database", "green")

        # If no database tracks or very few, fall back to filesystem scan
        if not main.music_tracks:
            safe_print("No tracks in database, scanning filesystem...", "yellow")
            main.music_tracks = library.scan_music_library(main.current_config, show_progress=False)

            if not main.music_tracks:
                safe_print("No music files found in configured library paths.", "red")
                safe_print("Run 'music-minion scan' to populate the database, or 'music-minion init' to set up library paths.", "yellow")
                return False

            safe_print(f"Scanned {len(main.music_tracks)} tracks from filesystem", "green")

    return True


def auto_export_if_enabled(playlist_id: int) -> None:
    """
    Auto-export a playlist if auto-export is enabled in config.

    Args:
        playlist_id: ID of the playlist to export
    """
    from . import main

    if not main.current_config.playlists.auto_export:
        return

    # Validate library paths exist
    if not main.current_config.music.library_paths:
        print("Warning: Cannot auto-export - no library paths configured", file=sys.stderr)
        return

    # Get library root from config
    library_root = Path(main.current_config.music.library_paths[0]).expanduser()

    # Silently export in the background - don't interrupt user workflow
    try:
        playlist_export.auto_export_playlist(
            playlist_id=playlist_id,
            export_formats=main.current_config.playlists.export_formats,
            library_root=library_root,
            use_relative_paths=main.current_config.playlists.use_relative_paths
        )
    except (ValueError, FileNotFoundError, ImportError, OSError) as e:
        # Expected errors - log but don't interrupt workflow
        print(f"Auto-export failed: {e}", file=sys.stderr)
    except Exception as e:
        # Unexpected errors - log for debugging
        print(f"Unexpected error during auto-export: {e}", file=sys.stderr)
