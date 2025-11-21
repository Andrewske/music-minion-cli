"""
Track operation command handlers for Music Minion CLI.

Handles: add, remove (adding/removing tracks to/from playlists)
"""

from typing import List, Tuple

from loguru import logger

from music_minion.context import AppContext
from music_minion.core import database
from music_minion.core.output import log
from music_minion.domain import playlists
from music_minion.domain import library
from music_minion import helpers


def handle_add_command(ctx: AppContext, args: List[str]) -> Tuple[AppContext, bool]:
    """Handle add command - add current track to playlist.

    Args:
        ctx: Application context
        args: Command arguments

    Returns:
        (updated_context, should_continue)
    """
    if not ctx.player_state.current_track:
        log("No track is currently playing", "warning")
        return ctx, True

    if not args:
        log("Error: Please specify playlist name", "error")
        log("Usage: add <playlist_name>", "info")
        return ctx, True

    name = ' '.join(args)

    # Get active library for better error messages
    with database.get_db_connection() as conn:
        cursor = conn.execute("SELECT provider FROM active_library WHERE id = 1")
        row = cursor.fetchone()
        active_library = row['provider'] if row else 'local'

    pl = playlists.get_playlist_by_name(name)

    if not pl:
        log(f"❌ Playlist '{name}' not found in {active_library} library", "error")
        if active_library != 'local':
            log(f"   Tip: Switch to local library with 'library active local' to access local playlists", "info")
        return ctx, True

    # Get current track ID - prefer using the cached ID from player state
    track_id = ctx.player_state.current_track_id

    # Fallback to path lookup for backward compatibility
    if not track_id:
        db_track = database.get_track_by_path(ctx.player_state.current_track)
        if not db_track:
            log("❌ Could not find current track in database", "error")
            return ctx, True
        track_id = db_track['id']

    # Fetch full track info from database using track_id
    db_track = database.get_track_by_id(track_id)
    if not db_track:
        log("❌ Could not find current track in database", "error")
        return ctx, True

    try:
        # Use unified CRUD function which handles both local and SoundCloud sync
        if playlists.add_track_to_playlist(pl['id'], track_id):
            # Find current track info for display
            current_track = None
            for track in ctx.music_tracks:
                if track.local_path == ctx.player_state.current_track:
                    current_track = track
                    break

            if current_track:
                display_name = library.get_display_name(current_track)
            else:
                display_name = "current track"

            # Check if this was a SoundCloud playlist for better messaging
            if pl.get('soundcloud_playlist_id'):
                log(f"✅ Added to SoundCloud playlist '{name}': {display_name}", "info")
            else:
                log(f"✅ Added to '{name}': {display_name}", "info")

            # Auto-export if enabled (only for local playlists)
            helpers.auto_export_if_enabled(pl['id'], ctx)
        else:
            log(f"Track is already in playlist '{name}'", "warning")
        return ctx, True
    except ValueError as e:
        logger.error(f"ValueError in add_command: {e}")
        log(f"❌ Error: {e}", "error")
        return ctx, True
    except Exception as e:
        logger.exception(f"Error adding track to playlist '{name}'")
        log(f"❌ Error adding track to playlist: {e}", "error")
        return ctx, True


def handle_remove_command(ctx: AppContext, args: List[str]) -> Tuple[AppContext, bool]:
    """Handle remove command - remove current track from playlist.

    Args:
        ctx: Application context
        args: Command arguments

    Returns:
        (updated_context, should_continue)
    """
    if not ctx.player_state.current_track:
        log("No track is currently playing", "warning")
        return ctx, True

    if not args:
        log("Error: Please specify playlist name", "error")
        log("Usage: remove <playlist_name>", "info")
        return ctx, True

    name = ' '.join(args)

    # Get active library for better error messages
    with database.get_db_connection() as conn:
        cursor = conn.execute("SELECT provider FROM active_library WHERE id = 1")
        row = cursor.fetchone()
        active_library = row['provider'] if row else 'local'

    pl = playlists.get_playlist_by_name(name)

    if not pl:
        log(f"❌ Playlist '{name}' not found in {active_library} library", "error")
        if active_library != 'local':
            log(f"   Tip: Switch to local library with 'library active local' to access local playlists", "info")
        return ctx, True

    # Get current track ID - prefer using the cached ID from player state
    track_id = ctx.player_state.current_track_id

    # Fallback to path lookup for backward compatibility
    if not track_id:
        db_track = database.get_track_by_path(ctx.player_state.current_track)
        if not db_track:
            log("❌ Could not find current track in database", "error")
            return ctx, True
        track_id = db_track['id']

    # Fetch full track info from database using track_id
    db_track = database.get_track_by_id(track_id)
    if not db_track:
        log("❌ Could not find current track in database", "error")
        return ctx, True

    try:
        # Use unified CRUD function which handles both local and SoundCloud sync
        if playlists.remove_track_from_playlist(pl['id'], track_id):
            # Find current track info for display
            current_track = None
            for track in ctx.music_tracks:
                if track.local_path == ctx.player_state.current_track:
                    current_track = track
                    break

            if current_track:
                display_name = library.get_display_name(current_track)
            else:
                display_name = "current track"

            # Check if this was a SoundCloud playlist for better messaging
            if pl.get('soundcloud_playlist_id'):
                log(f"✅ Removed from SoundCloud playlist '{name}': {display_name}", "info")
            else:
                log(f"✅ Removed from '{name}': {display_name}", "info")

            # Auto-export if enabled (only for local playlists)
            helpers.auto_export_if_enabled(pl['id'], ctx)
        else:
            log(f"Track is not in playlist '{name}'", "warning")
        return ctx, True
    except ValueError as e:
        logger.error(f"ValueError in remove_command: {e}")
        log(f"❌ Error: {e}", "error")
        return ctx, True
    except Exception as e:
        logger.exception(f"Error removing track from playlist '{name}'")
        log(f"❌ Error removing track from playlist: {e}", "error")
        return ctx, True


def handle_metadata_command(ctx: AppContext, args: List[str]) -> Tuple[AppContext, bool]:
    """Handle metadata command - show metadata editor for current track.

    Note: Metadata editing is only supported for local files, not streaming tracks.

    Args:
        ctx: Application context
        args: Command arguments (unused)

    Returns:
        (updated_context, should_continue)
    """
    if not ctx.player_state.current_track:
        log("No track is currently playing", "warning")
        return ctx, True

    # Get track ID from player state (works for both local and streaming tracks)
    track_id = ctx.player_state.current_track_id

    # Fallback to path lookup for backward compatibility
    if not track_id:
        db_track = database.get_track_by_path(ctx.player_state.current_track)
        if not db_track:
            log("❌ Could not find current track in database", "error")
            return ctx, True
        track_id = db_track['id']

    # Get full track info from database
    db_track = database.get_track_by_id(track_id)
    if not db_track:
        log("❌ Could not find current track in database", "error")
        return ctx, True

    # Check if this is a streaming track
    if not db_track.get('local_path') or not db_track.get('local_path').strip():
        # This is a streaming track - cannot edit metadata
        log("⚠️  Cannot edit metadata for streaming tracks", "warning")
        log(f"   Track: {db_track.get('artist')} - {db_track.get('title')}", "info")
        if db_track.get('soundcloud_id'):
            log("   Source: SoundCloud", "info")
        elif db_track.get('spotify_id'):
            log("   Source: Spotify", "info")
        elif db_track.get('youtube_id'):
            log("   Source: YouTube", "info")
        return ctx, True

    # Signal to blessed UI to open metadata editor
    # This will be handled via InternalCommand in keyboard handler
    from music_minion.ui.blessed.state import InternalCommand
    from music_minion.ui.blessed.events.commands.metadata_handlers import handle_show_metadata_editor

    # For non-blessed mode, show error
    if not hasattr(ctx, 'ui_state'):
        log("⚠️  Metadata editor only available in blessed UI mode", "warning")
        return ctx, True

    # In blessed mode, this command is handled via internal command
    # The blessed app will call handle_show_metadata_editor
    log(f"Opening metadata editor for: {db_track.get('artist')} - {db_track.get('title')}", "info")

    return ctx, True
