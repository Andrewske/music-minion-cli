"""
Track operation command handlers for Music Minion CLI.

Handles: add, remove (adding/removing tracks to/from playlists)
"""

from typing import List

from ..domain import playlists
from ..domain import library


def get_player_state():
    """Get current player state from main module."""
    from .. import main
    return main.current_player_state


def get_music_tracks():
    """Get music tracks from main module."""
    from .. import main
    return main.music_tracks


def get_current_track_id():
    """Get current track database ID."""
    from .. import main
    return main.get_current_track_id()


def auto_export_if_enabled(playlist_id: int) -> None:
    """Auto-export playlist if enabled."""
    from .. import main
    return main.auto_export_if_enabled(playlist_id)


def handle_add_command(args: List[str]) -> bool:
    """Handle add command - add current track to playlist."""
    current_player_state = get_player_state()
    music_tracks = get_music_tracks()

    if not current_player_state.current_track:
        print("No track is currently playing")
        return True

    if not args:
        print("Error: Please specify playlist name")
        print("Usage: add <playlist_name>")
        return True

    name = ' '.join(args)
    pl = playlist.get_playlist_by_name(name)

    if not pl:
        print(f"❌ Playlist '{name}' not found")
        return True

    # Get current track ID
    track_id = get_current_track_id()
    if not track_id:
        print("❌ Could not find current track in database")
        return True

    try:
        if playlist.add_track_to_playlist(pl['id'], track_id):
            # Find current track info for display
            current_track = None
            for track in music_tracks:
                if track.file_path == current_player_state.current_track:
                    current_track = track
                    break

            if current_track:
                print(f"✅ Added to '{name}': {library.get_display_name(current_track)}")
            else:
                print(f"✅ Added current track to playlist: {name}")

            # Auto-export if enabled
            auto_export_if_enabled(pl['id'])
        else:
            print(f"Track is already in playlist '{name}'")
        return True
    except ValueError as e:
        print(f"❌ Error: {e}")
        return True
    except Exception as e:
        print(f"❌ Error adding track to playlist: {e}")
        return True


def handle_remove_command(args: List[str]) -> bool:
    """Handle remove command - remove current track from playlist."""
    current_player_state = get_player_state()
    music_tracks = get_music_tracks()

    if not current_player_state.current_track:
        print("No track is currently playing")
        return True

    if not args:
        print("Error: Please specify playlist name")
        print("Usage: remove <playlist_name>")
        return True

    name = ' '.join(args)
    pl = playlist.get_playlist_by_name(name)

    if not pl:
        print(f"❌ Playlist '{name}' not found")
        return True

    # Get current track ID
    track_id = get_current_track_id()
    if not track_id:
        print("❌ Could not find current track in database")
        return True

    try:
        if playlist.remove_track_from_playlist(pl['id'], track_id):
            # Find current track info for display
            current_track = None
            for track in music_tracks:
                if track.file_path == current_player_state.current_track:
                    current_track = track
                    break

            if current_track:
                print(f"✅ Removed from '{name}': {library.get_display_name(current_track)}")
            else:
                print(f"✅ Removed current track from playlist: {name}")

            # Auto-export if enabled
            auto_export_if_enabled(pl['id'])
        else:
            print(f"Track is not in playlist '{name}'")
        return True
    except ValueError as e:
        print(f"❌ Error: {e}")
        return True
    except Exception as e:
        print(f"❌ Error removing track from playlist: {e}")
        return True
