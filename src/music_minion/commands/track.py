"""
Track operation command handlers for Music Minion CLI.

Handles: add, remove (adding/removing tracks to/from playlists)
"""

import logging
from typing import List, Tuple

from music_minion.context import AppContext
from music_minion.core import database
from music_minion.domain import playlists
from music_minion.domain import library
from music_minion import helpers

logger = logging.getLogger(__name__)


def handle_add_command(ctx: AppContext, args: List[str]) -> Tuple[AppContext, bool]:
    """Handle add command - add current track to playlist.

    Args:
        ctx: Application context
        args: Command arguments

    Returns:
        (updated_context, should_continue)
    """
    if not ctx.player_state.current_track:
        print("No track is currently playing")
        return ctx, True

    if not args:
        print("Error: Please specify playlist name")
        print("Usage: add <playlist_name>")
        return ctx, True

    name = ' '.join(args)

    # Get active library for better error messages
    with database.get_db_connection() as conn:
        cursor = conn.execute("SELECT provider FROM active_library WHERE id = 1")
        row = cursor.fetchone()
        active_library = row['provider'] if row else 'local'

    pl = playlists.get_playlist_by_name(name)

    if not pl:
        print(f"❌ Playlist '{name}' not found in {active_library} library")
        if active_library != 'local':
            print(f"   Tip: Switch to local library with 'library active local' to access local playlists")
        return ctx, True

    # Get current track ID - prefer using the cached ID from player state
    track_id = ctx.player_state.current_track_id

    # Fallback to path lookup for backward compatibility
    if not track_id:
        db_track = database.get_track_by_path(ctx.player_state.current_track)
        if not db_track:
            print("❌ Could not find current track in database")
            return ctx, True
        track_id = db_track['id']

    # Fetch full track info from database using track_id
    db_track = database.get_track_by_id(track_id)
    if not db_track:
        print("❌ Could not find current track in database")
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
                print(f"✅ Added to SoundCloud playlist '{name}': {display_name}")
            else:
                print(f"✅ Added to '{name}': {display_name}")

            # Auto-export if enabled (only for local playlists)
            helpers.auto_export_if_enabled(pl['id'], ctx)
        else:
            print(f"Track is already in playlist '{name}'")
        return ctx, True
    except ValueError as e:
        logger.error(f"ValueError in add_command: {e}")
        print(f"❌ Error: {e}")
        return ctx, True
    except Exception as e:
        logger.exception(f"Error adding track to playlist '{name}'")
        print(f"❌ Error adding track to playlist: {e}")
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
        print("No track is currently playing")
        return ctx, True

    if not args:
        print("Error: Please specify playlist name")
        print("Usage: remove <playlist_name>")
        return ctx, True

    name = ' '.join(args)

    # Get active library for better error messages
    with database.get_db_connection() as conn:
        cursor = conn.execute("SELECT provider FROM active_library WHERE id = 1")
        row = cursor.fetchone()
        active_library = row['provider'] if row else 'local'

    pl = playlists.get_playlist_by_name(name)

    if not pl:
        print(f"❌ Playlist '{name}' not found in {active_library} library")
        if active_library != 'local':
            print(f"   Tip: Switch to local library with 'library active local' to access local playlists")
        return ctx, True

    # Get current track ID - prefer using the cached ID from player state
    track_id = ctx.player_state.current_track_id

    # Fallback to path lookup for backward compatibility
    if not track_id:
        db_track = database.get_track_by_path(ctx.player_state.current_track)
        if not db_track:
            print("❌ Could not find current track in database")
            return ctx, True
        track_id = db_track['id']

    # Fetch full track info from database using track_id
    db_track = database.get_track_by_id(track_id)
    if not db_track:
        print("❌ Could not find current track in database")
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
                print(f"✅ Removed from SoundCloud playlist '{name}': {display_name}")
            else:
                print(f"✅ Removed from '{name}': {display_name}")

            # Auto-export if enabled (only for local playlists)
            helpers.auto_export_if_enabled(pl['id'], ctx)
        else:
            print(f"Track is not in playlist '{name}'")
        return ctx, True
    except ValueError as e:
        logger.error(f"ValueError in remove_command: {e}")
        print(f"❌ Error: {e}")
        return ctx, True
    except Exception as e:
        logger.exception(f"Error removing track from playlist '{name}'")
        print(f"❌ Error removing track from playlist: {e}")
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
        print("No track is currently playing")
        return ctx, True

    # Get track ID from player state (works for both local and streaming tracks)
    track_id = ctx.player_state.current_track_id

    # Fallback to path lookup for backward compatibility
    if not track_id:
        db_track = database.get_track_by_path(ctx.player_state.current_track)
        if not db_track:
            print("❌ Could not find current track in database")
            return ctx, True
        track_id = db_track['id']

    # Get full track info from database
    db_track = database.get_track_by_id(track_id)
    if not db_track:
        print("❌ Could not find current track in database")
        return ctx, True

    # Check if this is a streaming track
    if not db_track.get('local_path') or not db_track.get('local_path').strip():
        # This is a streaming track - cannot edit metadata
        print("⚠️  Cannot edit metadata for streaming tracks")
        print(f"   Track: {db_track.get('artist')} - {db_track.get('title')}")
        if db_track.get('soundcloud_id'):
            print("   Source: SoundCloud")
        elif db_track.get('spotify_id'):
            print("   Source: Spotify")
        elif db_track.get('youtube_id'):
            print("   Source: YouTube")
        return ctx, True

    # Signal to blessed UI to open metadata editor
    # This will be handled via InternalCommand in keyboard handler
    from music_minion.ui.blessed.state import InternalCommand
    from music_minion.ui.blessed.events.commands.metadata_handlers import handle_show_metadata_editor

    # For non-blessed mode, show error
    if not hasattr(ctx, 'ui_state'):
        print("⚠️  Metadata editor only available in blessed UI mode")
        return ctx, True

    # In blessed mode, this command is handled via internal command
    # The blessed app will call handle_show_metadata_editor
    print(f"Opening metadata editor for: {db_track.get('artist')} - {db_track.get('title')}")

    return ctx, True
