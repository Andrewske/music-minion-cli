"""Command execution."""

import io
from contextlib import redirect_stdout, redirect_stderr
from ....context import AppContext
from ..state import UIState, add_history_line, set_feedback, add_command_to_history, show_playlist_palette
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
    from ....domain import playlists
    from ....domain import playback
    from ....core import database

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
            # Convert first track to library.Track and play
            first_track = database.db_track_to_library_track(playlist_tracks[0])

            # Import play_track from playback commands
            from ....commands.playback import play_track

            # Play the first track
            ctx, _ = play_track(ctx, first_track, playlist_position=0)

            # Show feedback
            artist = first_track.artist or 'Unknown'
            title = first_track.title or 'Unknown'
            ui_state = add_history_line(ui_state, f"🎵 Now playing: {artist} - {title}", 'white')
            ui_state = set_feedback(ui_state, f"✓ Playing {playlist_name}", "✓")
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
    from ....domain import playlists
    from ....domain import playback
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
