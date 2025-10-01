"""
Track operation command handlers for Music Minion CLI.

Handles: add, remove (adding/removing tracks to/from playlists)
"""

from typing import List, Tuple

from ..context import AppContext
from ..core import database
from ..domain import playlists
from ..domain import library
from .. import helpers


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
    pl = playlists.get_playlist_by_name(name)

    if not pl:
        print(f"❌ Playlist '{name}' not found")
        return ctx, True

    # Get current track ID
    db_track = database.get_track_by_path(ctx.player_state.current_track)
    if not db_track:
        print("❌ Could not find current track in database")
        return ctx, True

    track_id = db_track['id']

    try:
        if playlists.add_track_to_playlist(pl['id'], track_id):
            # Find current track info for display
            current_track = None
            for track in ctx.music_tracks:
                if track.file_path == ctx.player_state.current_track:
                    current_track = track
                    break

            if current_track:
                print(f"✅ Added to '{name}': {library.get_display_name(current_track)}")
            else:
                print(f"✅ Added current track to playlist: {name}")

            # Auto-export if enabled
            helpers.auto_export_if_enabled(pl['id'], ctx)
        else:
            print(f"Track is already in playlist '{name}'")
        return ctx, True
    except ValueError as e:
        print(f"❌ Error: {e}")
        return ctx, True
    except Exception as e:
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
    pl = playlists.get_playlist_by_name(name)

    if not pl:
        print(f"❌ Playlist '{name}' not found")
        return ctx, True

    # Get current track ID
    db_track = database.get_track_by_path(ctx.player_state.current_track)
    if not db_track:
        print("❌ Could not find current track in database")
        return ctx, True

    track_id = db_track['id']

    try:
        if playlists.remove_track_from_playlist(pl['id'], track_id):
            # Find current track info for display
            current_track = None
            for track in ctx.music_tracks:
                if track.file_path == ctx.player_state.current_track:
                    current_track = track
                    break

            if current_track:
                print(f"✅ Removed from '{name}': {library.get_display_name(current_track)}")
            else:
                print(f"✅ Removed current track from playlist: {name}")

            # Auto-export if enabled
            helpers.auto_export_if_enabled(pl['id'], ctx)
        else:
            print(f"Track is not in playlist '{name}'")
        return ctx, True
    except ValueError as e:
        print(f"❌ Error: {e}")
        return ctx, True
    except Exception as e:
        print(f"❌ Error removing track from playlist: {e}")
        return ctx, True
