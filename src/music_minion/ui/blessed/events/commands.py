"""Command execution."""

import io
from contextlib import redirect_stdout, redirect_stderr
from music_minion.context import AppContext
from ..state import (
    UIState,
    add_history_line,
    set_feedback,
    add_command_to_history,
    show_playlist_palette,
    start_wizard,
    show_track_viewer,
    hide_track_viewer
)
from ..components.palette import load_playlist_items


def parse_command_line(line: str) -> tuple[str, list[str]]:
    """
    Parse command line into command and arguments.

    Args:
        line: Full command line (e.g., "playlist new smart test")

    Returns:
        Tuple of (command, args)
    """
    parts = line.strip().split()
    if not parts:
        return "", []
    return parts[0], parts[1:]


def execute_command(ctx: AppContext, ui_state: UIState, command_line: str) -> tuple[AppContext, UIState, bool]:
    """
    Execute command and return updated state.

    Args:
        ctx: Application context
        ui_state: UI state
        command_line: Full command line string

    Returns:
        Tuple of (updated AppContext, updated UIState, should_quit)
    """
    # Parse command
    command, args = parse_command_line(command_line)

    if not command:
        return ctx, ui_state, False

    # Special case: QUIT signal from keyboard handler
    if command == 'QUIT':
        return ctx, ui_state, True

    # Special case: Playlist selection from palette
    if command == '__SELECT_PLAYLIST__':
        playlist_name = ' '.join(args)
        ctx, ui_state = _handle_playlist_selection(ctx, ui_state, playlist_name)
        return ctx, ui_state, False

    # Special case: Playlist deletion from palette
    if command == '__DELETE_PLAYLIST__':
        playlist_name = ' '.join(args)
        ctx, ui_state = _handle_playlist_deletion(ctx, ui_state, playlist_name)
        return ctx, ui_state, False

    # Special case: Save wizard playlist
    if command == '__SAVE_WIZARD_PLAYLIST__':
        ctx, ui_state = _handle_wizard_save(ctx, ui_state)
        return ctx, ui_state, False

    # Special case: Show track viewer
    if command == '__SHOW_TRACK_VIEWER__':
        playlist_name = ' '.join(args)
        ctx, ui_state = _handle_show_track_viewer(ctx, ui_state, playlist_name)
        return ctx, ui_state, False

    # Special case: Play track from viewer
    if command == '__PLAY_TRACK_FROM_VIEWER__':
        if len(args) >= 2:
            playlist_id = int(args[0])
            track_index = int(args[1])
            ctx, ui_state = _handle_play_track_from_viewer(ctx, ui_state, playlist_id, track_index)
        return ctx, ui_state, False

    # Special case: Remove track from playlist
    if command == '__REMOVE_TRACK_FROM_PLAYLIST__':
        if len(args) >= 2:
            track_id = int(args[0])
            playlist_name = ' '.join(args[1:])
            ctx, ui_state = _handle_remove_track_from_playlist(ctx, ui_state, track_id, playlist_name)
        return ctx, ui_state, False

    # Add command to history display
    ui_state = add_history_line(ui_state, f"> {command_line}", 'cyan')

    # Add command to command history (for up/down arrow navigation)
    ui_state = add_command_to_history(ui_state, command_line)

    # Capture output from command execution
    output_buffer = io.StringIO()
    error_buffer = io.StringIO()

    try:
        with redirect_stdout(output_buffer), redirect_stderr(error_buffer):
            # Import router for command handling
            # This is a lazy import to avoid circular dependencies
            from music_minion import router

            # Execute command with proper AppContext signature
            ctx, should_continue = router.handle_command(ctx, command, args)

            if not should_continue:
                # Command requested exit (quit/exit command)
                return ctx, ui_state, True

    except Exception as e:
        # Add error to history
        ui_state = add_history_line(ui_state, f"Error: {e}", 'red')
        return ctx, ui_state, False

    # Get captured output
    stdout_output = output_buffer.getvalue()
    stderr_output = error_buffer.getvalue()

    # Add output to history (split by lines)
    if stdout_output:
        for line in stdout_output.strip().split('\n'):
            if line:
                ui_state = add_history_line(ui_state, line, 'white')

    if stderr_output:
        for line in stderr_output.strip().split('\n'):
            if line:
                ui_state = add_history_line(ui_state, line, 'red')

    # Set feedback for certain commands
    if command in ['love', 'like', 'archive', 'skip']:
        ui_state = set_feedback(ui_state, f"✓ {command.capitalize()}", "✓")

    # Process UI actions from returned context
    if ctx.ui_action:
        ctx, ui_state = _process_ui_action(ctx, ui_state)

    return ctx, ui_state, False


def _process_ui_action(ctx: AppContext, ui_state: UIState) -> tuple[AppContext, UIState]:
    """
    Process UI action from command handler.

    Args:
        ctx: Application context with ui_action set
        ui_state: Current UI state

    Returns:
        Tuple of (updated AppContext with ui_action cleared, updated UIState)
    """
    action = ctx.ui_action

    if action['type'] == 'show_playlist_palette':
        # Load playlists and show palette
        playlist_items = load_playlist_items()
        ui_state = show_playlist_palette(ui_state, playlist_items)

    elif action['type'] == 'start_wizard':
        # Start wizard with provided data
        wizard_type = action.get('wizard_type', 'smart_playlist')
        wizard_data = action.get('wizard_data', {})
        ui_state = start_wizard(ui_state, wizard_type, wizard_data)

    elif action['type'] == 'show_track_viewer':
        # Show track viewer for playlist
        playlist_name = action.get('playlist_name', '')
        ctx, ui_state = _handle_show_track_viewer(ctx, ui_state, playlist_name)

    # Clear the ui_action after processing
    ctx = ctx.with_ui_action(None)

    return ctx, ui_state


def _handle_playlist_selection(ctx: AppContext, ui_state: UIState, playlist_name: str) -> tuple[AppContext, UIState]:
    """
    Handle playlist selection from palette.

    Args:
        ctx: Application context
        ui_state: Current UI state
        playlist_name: Name of selected playlist

    Returns:
        Tuple of (updated AppContext, updated UIState)
    """
    # Import here to avoid circular dependencies
    from music_minion.domain import playlists
    from music_minion.domain import playback
    from music_minion.core import database

    # Get playlist by name
    pl = playlists.get_playlist_by_name(playlist_name)
    if not pl:
        ui_state = add_history_line(ui_state, f"❌ Playlist '{playlist_name}' not found", 'red')
        return ctx, ui_state

    # Activate playlist
    if playlists.set_active_playlist(pl['id']):
        ui_state = add_history_line(ui_state, f"✅ Activated playlist: {playlist_name}", 'green')

        # Get playlist tracks
        playlist_tracks = playlists.get_playlist_tracks(pl['id'])

        if playlist_tracks:
            # Import play_track and helpers from playback commands
            from music_minion.commands.playback import play_track, get_available_tracks
            from music_minion.domain import library

            # Check shuffle mode to determine which track to play
            shuffle_enabled = playback.get_shuffle_mode()

            selected_track = None
            track_position = None

            if shuffle_enabled:
                # Shuffle mode: Pick random track from available (non-archived) tracks
                available_tracks = get_available_tracks(ctx)
                if available_tracks:
                    # Filter to only tracks in this playlist
                    playlist_paths = {t['file_path'] for t in playlist_tracks}
                    playlist_available = [t for t in available_tracks if t.file_path in playlist_paths]

                    if playlist_available:
                        selected_track = library.get_random_track(playlist_available)
                        # Don't set position for shuffle mode
                        track_position = None
            else:
                # Sequential mode: Check for saved position, otherwise use first track
                saved_position = playback.get_playlist_position(pl['id'])
                if saved_position:
                    track_id, position = saved_position
                    # Find the saved track in playlist
                    for i, t in enumerate(playlist_tracks):
                        if t['id'] == track_id:
                            selected_track = database.db_track_to_library_track(t)
                            track_position = i
                            break

                # If no saved position or track not found, use first track
                if selected_track is None:
                    selected_track = database.db_track_to_library_track(playlist_tracks[0])
                    track_position = 0

            # Play the selected track
            if selected_track:
                ctx, _ = play_track(ctx, selected_track, playlist_position=track_position)

                # Show feedback
                artist = selected_track.artist or 'Unknown'
                title = selected_track.title or 'Unknown'
                mode_indicator = "🔀" if shuffle_enabled else "▶️"
                ui_state = add_history_line(ui_state, f"{mode_indicator} Now playing: {artist} - {title}", 'white')
                ui_state = set_feedback(ui_state, f"✓ Playing {playlist_name}", "✓")
            else:
                ui_state = add_history_line(ui_state, f"⚠️  No available tracks in playlist", 'yellow')
        else:
            ui_state = add_history_line(ui_state, f"⚠️  Playlist is empty", 'yellow')
    else:
        ui_state = add_history_line(ui_state, f"❌ Failed to activate playlist", 'red')

    return ctx, ui_state


def _handle_playlist_deletion(ctx: AppContext, ui_state: UIState, playlist_name: str) -> tuple[AppContext, UIState]:
    """
    Handle playlist deletion from palette.

    Args:
        ctx: Application context
        ui_state: Current UI state
        playlist_name: Name of playlist to delete

    Returns:
        Tuple of (updated AppContext, updated UIState)
    """
    # Import here to avoid circular dependencies
    from music_minion.domain import playlists
    from music_minion.domain import playback
    from dataclasses import replace

    # Get playlist by name
    pl = playlists.get_playlist_by_name(playlist_name)
    if not pl:
        ui_state = add_history_line(ui_state, f"❌ Playlist '{playlist_name}' not found", 'red')
        # Refresh playlist items
        playlist_items = load_playlist_items()
        ui_state = show_playlist_palette(ui_state, playlist_items)
        return ctx, ui_state

    # Clear position tracking before deleting
    playback.clear_playlist_position(pl['id'])

    # Delete playlist
    if playlists.delete_playlist(pl['id']):
        ui_state = add_history_line(ui_state, f"✅ Deleted playlist: {playlist_name}", 'green')
        ui_state = set_feedback(ui_state, f"✓ Deleted {playlist_name}", "✓")
    else:
        ui_state = add_history_line(ui_state, f"❌ Failed to delete playlist", 'red')

    # Refresh playlist items and stay in palette
    playlist_items = load_playlist_items()

    # If list is now empty, hide palette
    if not playlist_items:
        ui_state = ui_state  # Keep current state but palette will be hidden
        from ..state import hide_palette
        ui_state = hide_palette(ui_state)
        ui_state = add_history_line(ui_state, "No playlists remaining", 'white')
    else:
        # Stay in playlist palette with refreshed list
        # Adjust selection if needed
        new_selected = min(ui_state.palette_selected, len(playlist_items) - 1)
        ui_state = show_playlist_palette(ui_state, playlist_items)
        ui_state = replace(ui_state, palette_selected=new_selected)

    return ctx, ui_state


def _handle_wizard_save(ctx: AppContext, ui_state: UIState) -> tuple[AppContext, UIState]:
    """
    Handle saving playlist from wizard.

    Args:
        ctx: Application context
        ui_state: Current UI state (wizard must be active)

    Returns:
        Tuple of (updated AppContext, updated UIState)
    """
    # Import here to avoid circular dependencies
    from music_minion.domain import playlists
    from music_minion.domain.playlists import filters as playlist_filters
    from ..state import cancel_wizard

    wizard_data = ui_state.wizard_data
    playlist_name = wizard_data.get('name', 'Untitled')
    filters = wizard_data.get('filters', [])

    try:
        # Create the playlist
        playlist_id = playlists.create_playlist(playlist_name, 'smart', description=None)

        # Add all filters
        for f in filters:
            playlist_filters.add_filter(
                playlist_id,
                f['field'],
                f['operator'],
                f['value'],
                f.get('conjunction', 'AND')
            )

        # Update track count
        playlists.update_playlist_track_count(playlist_id)

        # Success message
        matching_count = wizard_data.get('matching_count', 0)
        ui_state = add_history_line(ui_state, f"✅ Created smart playlist: {playlist_name}", 'green')
        ui_state = add_history_line(ui_state, f"   {matching_count} tracks match your filters", 'white')
        ui_state = set_feedback(ui_state, f"✓ Created {playlist_name}", "✓")

        # Auto-export if enabled (import from helpers)
        try:
            from music_minion import helpers
            helpers.auto_export_if_enabled(playlist_id)
        except Exception:
            pass  # Ignore auto-export errors

    except ValueError as e:
        ui_state = add_history_line(ui_state, f"❌ Error: {e}", 'red')
    except Exception as e:
        ui_state = add_history_line(ui_state, f"❌ Error creating playlist: {e}", 'red')

    # Close wizard
    ui_state = cancel_wizard(ui_state)

    return ctx, ui_state


def _handle_show_track_viewer(ctx: AppContext, ui_state: UIState, playlist_name: str) -> tuple[AppContext, UIState]:
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


def _handle_play_track_from_viewer(ctx: AppContext, ui_state: UIState, playlist_id: int, track_index: int) -> tuple[AppContext, UIState]:
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
    from music_minion.domain import playlists
    from music_minion.core import database
    from music_minion.commands.playback import play_track

    # Get playlist tracks
    tracks = playlists.get_playlist_tracks(playlist_id)

    if track_index >= len(tracks):
        ui_state = add_history_line(ui_state, f"❌ Invalid track index", 'red')
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


def _handle_remove_track_from_playlist(ctx: AppContext, ui_state: UIState, track_id: int, playlist_name: str) -> tuple[AppContext, UIState]:
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
    from dataclasses import replace

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

    except Exception as e:
        ui_state = add_history_line(ui_state, f"❌ Error removing track: {e}", 'red')

    return ctx, ui_state
