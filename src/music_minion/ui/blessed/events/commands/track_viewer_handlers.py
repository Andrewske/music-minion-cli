"""Track viewer command handlers."""

from dataclasses import replace
from music_minion.context import AppContext
from music_minion.ui.blessed.state import (
    UIState,
    add_history_line,
    set_feedback,
    show_track_viewer,
    hide_track_viewer,
)


def handle_show_track_viewer(ctx: AppContext, ui_state: UIState, playlist_name: str) -> tuple[AppContext, UIState]:
    """
    Handle showing track viewer for a playlist.

    Args:
        ctx: Application context
        ui_state: Current UI state
        playlist_name: Name of playlist to view

    Returns:
        Tuple of (updated AppContext, updated UIState)
    """
    from music_minion.domain import playlists

    # Get playlist by name
    pl = playlists.get_playlist_by_name(playlist_name)
    if not pl:
        ui_state = add_history_line(ui_state, f"❌ Playlist '{playlist_name}' not found", 'red')
        return ctx, ui_state

    # Get playlist tracks
    tracks = playlists.get_playlist_tracks(pl['id'])

    # Show track viewer
    ui_state = show_track_viewer(
        ui_state,
        playlist_id=pl['id'],
        playlist_name=pl['name'],
        playlist_type=pl['type'],
        tracks=tracks
    )

    return ctx, ui_state


def handle_play_track_from_viewer(ctx: AppContext, ui_state: UIState, playlist_id: int, track_index: int) -> tuple[AppContext, UIState]:
    """
    Handle playing a track from the track viewer.

    Args:
        ctx: Application context
        ui_state: Current UI state
        playlist_id: ID of playlist containing track
        track_index: Index of track in viewer

    Returns:
        Tuple of (updated AppContext, updated UIState)
    """
    from music_minion.core import database
    from music_minion.commands.playback import play_track

    # Validate inputs
    if playlist_id < 0:
        ui_state = add_history_line(ui_state, f"❌ Invalid playlist ID: {playlist_id}", 'red')
        return ctx, ui_state

    if track_index < 0:
        ui_state = add_history_line(ui_state, f"❌ Invalid track index: {track_index}", 'red')
        return ctx, ui_state

    # Use tracks from UI state (already loaded)
    tracks = ui_state.track_viewer_tracks

    if track_index >= len(tracks):
        ui_state = add_history_line(ui_state, f"❌ Track index out of range: {track_index}", 'red')
        return ctx, ui_state

    # Get the selected track
    selected_track = tracks[track_index]

    # Convert to library track format
    library_track = database.db_track_to_library_track(selected_track)

    # Play the track with position for sequential mode
    ctx, _ = play_track(ctx, library_track, playlist_position=track_index)

    # Add feedback
    artist = library_track.artist or 'Unknown'
    title = library_track.title or 'Unknown'
    ui_state = add_history_line(ui_state, f"▶️  Now playing: {artist} - {title}", 'white')
    ui_state = set_feedback(ui_state, f"✓ Playing from viewer", "✓")

    # Keep viewer open
    return ctx, ui_state


def handle_remove_track_from_playlist(ctx: AppContext, ui_state: UIState, track_id: int, playlist_name: str) -> tuple[AppContext, UIState]:
    """
    Handle removing a track from a manual playlist.

    Args:
        ctx: Application context
        ui_state: Current UI state
        track_id: ID of track to remove
        playlist_name: Name of playlist

    Returns:
        Tuple of (updated AppContext, updated UIState)
    """
    from music_minion.domain import playlists

    # Validate inputs
    if track_id < 0:
        ui_state = add_history_line(ui_state, f"❌ Invalid track ID: {track_id}", 'red')
        ui_state = hide_track_viewer(ui_state)
        return ctx, ui_state

    if not playlist_name or not playlist_name.strip():
        ui_state = add_history_line(ui_state, "❌ Playlist name cannot be empty", 'red')
        ui_state = hide_track_viewer(ui_state)
        return ctx, ui_state

    # Get playlist by name
    pl = playlists.get_playlist_by_name(playlist_name)
    if not pl:
        ui_state = add_history_line(ui_state, f"❌ Playlist '{playlist_name}' not found", 'red')
        ui_state = hide_track_viewer(ui_state)
        return ctx, ui_state

    # Remove track from playlist
    try:
        playlists.remove_track_from_playlist(pl['id'], track_id)
        ui_state = add_history_line(ui_state, f"✅ Removed track from playlist", 'green')
        ui_state = set_feedback(ui_state, f"✓ Removed from {playlist_name}", "✓")

        # Refresh track list in viewer
        tracks = playlists.get_playlist_tracks(pl['id'])

        if not tracks:
            # No tracks left, close viewer
            ui_state = hide_track_viewer(ui_state)
            ui_state = add_history_line(ui_state, "Playlist is now empty", 'white')
        else:
            # Update viewer with new track list
            # Adjust selection if needed
            new_selected = min(ui_state.track_viewer_selected, len(tracks) - 1)
            ui_state = show_track_viewer(
                ui_state,
                playlist_id=pl['id'],
                playlist_name=pl['name'],
                playlist_type=pl['type'],
                tracks=tracks
            )
            ui_state = replace(ui_state, track_viewer_selected=new_selected)

    except (ValueError, KeyError, TypeError) as e:
        # Database or data structure errors
        ui_state = add_history_line(ui_state, f"❌ Error removing track: {e}", 'red')
    except OSError as e:
        # File system errors
        ui_state = add_history_line(ui_state, f"❌ Database error: {e}", 'red')

    return ctx, ui_state
