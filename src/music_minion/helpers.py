"""
Core utilities for Music Minion CLI.

Shared functions for command parsing, validation, and utilities.
"""

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

from music_minion.context import AppContext
from music_minion.core import config
from music_minion.core import database
from music_minion.domain import library
from music_minion.domain import playback
from music_minion.domain import ai
from music_minion.domain.playlists import exporters as playlist_export


def safe_print(ctx: AppContext, message: str, style: Optional[str] = None) -> None:
    """Print using Rich Console if available, otherwise fallback to regular print."""
    if ctx.console:
        if style:
            ctx.console.print(message, style=style)
        else:
            ctx.console.print(message)
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


def load_provider_states() -> Dict[str, Any]:
    """Load all provider authentication states from database.

    Returns:
        Dictionary mapping provider names to their state data
    """
    provider_states = {}

    # Load known providers
    for provider in ['soundcloud', 'spotify', 'youtube']:
        state = database.load_provider_state(provider)
        if state and state.get('authenticated'):
            # Store in format expected by resolver
            provider_states[provider] = {
                'authenticated': True,
                'token_data': state.get('auth_data', {}),
                'config': state.get('config', {})
            }

    return provider_states


def reload_tracks(ctx: AppContext) -> AppContext:
    """Reload tracks from database for active library.

    Args:
        ctx: Application context

    Returns:
        Updated context with reloaded tracks
    """
    from dataclasses import replace

    # Get all tracks from database for active library
    db_tracks = database.get_all_tracks()

    if db_tracks:
        # Convert database tracks to library Track objects
        tracks = [database.db_track_to_library_track(track) for track in db_tracks]

        # Filter out local files that no longer exist
        existing_tracks = []
        for track in tracks:
            # Keep provider tracks (no local_path or empty) and local tracks that still exist
            if not track.local_path or Path(track.local_path).exists():
                existing_tracks.append(track)

        # Update context with new tracks
        ctx = replace(ctx, music_tracks=existing_tracks)
        logger.info(f"Reloaded {len(existing_tracks)} tracks from database")

    return ctx


def ensure_library_loaded(ctx: AppContext) -> tuple[AppContext, bool]:
    """Ensure music library is loaded.

    Args:
        ctx: Application context

    Returns:
        (updated_context, success)
    """
    # Load provider states if not already loaded
    if not ctx.provider_states:
        provider_states = load_provider_states()
        if provider_states:
            # Create new context with provider states using dataclasses.replace
            from dataclasses import replace
            ctx = replace(ctx, provider_states=provider_states)

    # Auto-sync streaming providers on startup (incremental sync is fast)
    # Check what the active library is
    with database.get_db_connection() as conn:
        cursor = conn.execute("SELECT provider FROM active_library WHERE id = 1")
        row = cursor.fetchone()
        active_provider = row["provider"] if row else "local"

    # Auto-sync if active library is a streaming provider
    if active_provider == "spotify" and ctx.config.spotify.enabled:
        safe_print(ctx, "🔄 Auto-syncing Spotify library (incremental)...", "blue")
        from music_minion.commands import library as library_commands
        ctx, _ = library_commands.sync_library(ctx, active_provider, full=False)
        safe_print(ctx, "✓ Spotify sync complete", "green")
    elif active_provider == "soundcloud" and ctx.config.soundcloud.enabled:
        safe_print(ctx, "🔄 Auto-syncing SoundCloud library (incremental)...", "blue")
        from music_minion.commands import library as library_commands
        ctx, _ = library_commands.sync_library(ctx, active_provider, full=False)
        safe_print(ctx, "✓ SoundCloud sync complete", "green")

    if not ctx.music_tracks:
        safe_print(ctx, "Loading music library...", "blue")

        # Try to load from database first (much faster)
        db_tracks = database.get_all_tracks()
        if db_tracks:
            # Convert database tracks to library Track objects
            tracks = [database.db_track_to_library_track(track) for track in db_tracks]
            # Filter out files that no longer exist (only for local tracks)
            existing_tracks = []
            for track in tracks:
                # Keep provider tracks (no local_path or empty) and local tracks that still exist
                if not track.local_path or Path(track.local_path).exists():
                    existing_tracks.append(track)
            ctx = ctx.with_tracks(existing_tracks)
            safe_print(ctx, f"Loaded {len(existing_tracks)} tracks from database", "green")

        # If no database tracks or very few, fall back to filesystem scan
        if not ctx.music_tracks:
            safe_print(ctx, "No tracks in database, scanning filesystem...", "yellow")
            tracks = library.scan_music_library(ctx.config, show_progress=False)

            if not tracks:
                safe_print(ctx, "No music files found in configured library paths.", "red")
                safe_print(ctx, "Run 'music-minion scan' to populate the database, or 'music-minion init' to set up library paths.", "yellow")
                return ctx, False

            ctx = ctx.with_tracks(tracks)
            safe_print(ctx, f"Scanned {len(tracks)} tracks from filesystem", "green")

    return ctx, True


def auto_export_if_enabled(playlist_id: int, ctx: Optional[AppContext] = None) -> None:
    """
    Auto-export a playlist if auto-export is enabled in config.

    Only exports when active library is 'local'. Streaming libraries (soundcloud,
    spotify, youtube) do not support file export.

    Args:
        playlist_id: ID of the playlist to export
        ctx: Optional application context (for config access). If None, loads config.
    """
    # Get config from context or load it
    if ctx:
        cfg = ctx.config
    else:
        cfg = config.load_config()

    if not cfg.playlists.auto_export:
        return

    # Check active library - only export for local library
    with database.get_db_connection() as conn:
        cursor = conn.execute("SELECT provider FROM active_library WHERE id = 1")
        row = cursor.fetchone()
        active_library = row['provider'] if row else 'local'

    # Skip export for streaming libraries (soundcloud, spotify, youtube)
    # Export is only supported for local file libraries
    if active_library != 'local':
        return

    # Validate library paths exist
    if not cfg.music.library_paths:
        logger.warning("Cannot auto-export - no library paths configured")
        return

    # Get library root from config
    library_root = Path(cfg.music.library_paths[0]).expanduser()

    # Silently export in the background - don't interrupt user workflow
    try:
        playlist_export.auto_export_playlist(
            playlist_id=playlist_id,
            export_formats=cfg.playlists.export_formats,
            library_root=library_root,
            use_relative_paths=cfg.playlists.use_relative_paths
        )
    except (ValueError, FileNotFoundError, ImportError, OSError) as e:
        # Expected errors - log but don't interrupt workflow
        logger.exception("Auto-export failed")
    except Exception as e:
        # Unexpected errors - log for debugging
        logger.exception("Unexpected error during auto-export")


def check_and_handle_track_completion(ctx: AppContext) -> AppContext:
    """Check if current track has completed and handle auto-analysis and next track.

    Args:
        ctx: Application context

    Returns:
        Updated context (may have new player state and current track)
    """
    if not ctx.player_state.current_track:
        return ctx  # No track playing

    if not playback.is_mpv_running(ctx.player_state):
        return ctx  # Player not running

    # Check if track is still playing
    status = playback.get_player_status(ctx.player_state)
    position, duration, percent = playback.get_progress_info(ctx.player_state)

    # If track has ended (reached 100% or very close), trigger analysis and play next
    if duration > 0 and percent >= 99.0 and not status.get('playing', False):
        # Find the track that just finished
        finished_track = None
        for track in ctx.music_tracks:
            if track.local_path == ctx.player_state.current_track:
                finished_track = track
                break

        if finished_track:
            safe_print(ctx, f"✅ Finished: {library.get_display_name(finished_track)}", "green")

            # Check if track is archived (don't analyze archived tracks)
            # Use track ID from player state (multi-source support)
            track_id = ctx.player_state.current_track_id

            # Fallback to path lookup for backward compatibility
            if not track_id and ctx.player_state.current_track:
                db_track = database.get_track_by_path(ctx.player_state.current_track)
                if db_track:
                    track_id = db_track['id']

            if track_id:
                archived_tracks = database.get_archived_tracks()
                if track_id not in archived_tracks:
                    # Trigger auto-analysis
                    try:
                        safe_print(ctx, "🤖 Auto-analyzing completed track...", "cyan")
                        result = ai.analyze_and_tag_track(finished_track, 'auto_analysis')

                        if result['success'] and result['tags_added']:
                            safe_print(ctx, f"✅ Added {len(result['tags_added'])} AI tags: {', '.join(result['tags_added'])}", "green")
                        elif not result['success']:
                            error_msg = result.get('error', 'Unknown error')
                            if 'API key' in error_msg:
                                safe_print(ctx, "⚠️  AI analysis skipped: No API key configured (use 'ai setup <key>')", "yellow")
                            else:
                                safe_print(ctx, f"⚠️  AI analysis failed: {error_msg}", "yellow")
                    except Exception as e:
                        safe_print(ctx, f"⚠️  AI analysis error: {str(e)}", "yellow")

        # Clear current track and play next track automatically
        new_player_state = ctx.player_state._replace(current_track=None)
        ctx = ctx.with_player_state(new_player_state)

        # Auto-play next track
        safe_print(ctx, "⏭️  Auto-playing next track...", "blue")

        # Get available tracks (using playback commands helper)
        from .commands import playback as playback_commands
        available_tracks = playback_commands.get_available_tracks(ctx)

        # Remove the track that just finished from options if possible
        if finished_track and len(available_tracks) > 1:
            available_tracks = [t for t in available_tracks if t.local_path != finished_track.local_path]

        if available_tracks:
            next_track = library.get_random_track(available_tracks)
            if next_track:
                ctx, _ = playback_commands.play_track(ctx, next_track)
        else:
            safe_print(ctx, "No more tracks to play (all may be archived)", "red")

    return ctx


def sync_context_to_globals(ctx: AppContext) -> None:
    """Sync AppContext state to global variables (for dashboard mode compatibility).

    Args:
        ctx: Application context to sync from
    """
    import sys

    # Get main module
    if 'music_minion.main' in sys.modules:
        main_module = sys.modules['music_minion.main']
        main_module.current_player_state = ctx.player_state
        main_module.music_tracks = ctx.music_tracks
        main_module.current_config = ctx.config


def create_context_from_globals() -> AppContext:
    """Create AppContext from global variables (for dashboard mode initialization).

    Returns:
        AppContext initialized from global state
    """
    import sys
    from rich.console import Console

    # Get main module
    if 'music_minion.main' in sys.modules:
        main_module = sys.modules['music_minion.main']

        # Try to get console, create new if not available
        console = getattr(main_module, 'console', None) or Console()

        return AppContext(
            config=main_module.current_config,
            music_tracks=main_module.music_tracks,
            player_state=main_module.current_player_state,
            console=console
        )

    # Fallback: create empty context
    from .core.config import Config
    return AppContext.create(Config(), Console())
