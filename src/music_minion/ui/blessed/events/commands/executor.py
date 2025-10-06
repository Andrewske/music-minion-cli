"""Command execution logic."""

import io
from dataclasses import replace
from contextlib import redirect_stdout, redirect_stderr
from music_minion.context import AppContext
from music_minion.ui.blessed.state import (
    UIState,
    InternalCommand,
    PlaylistInfo,
    add_history_line,
    add_command_to_history,
    start_wizard,
    show_analytics_viewer,
)
from .playlist_handlers import handle_playlist_selection, handle_playlist_deletion
from .track_viewer_handlers import (
    handle_show_track_viewer,
    handle_play_track_from_viewer,
    handle_remove_track_from_playlist,
)
from .wizard_handlers import handle_wizard_save


def _show_analytics_viewer_if_data(ui_state: UIState, analytics_data: dict) -> UIState:
    """
    Show analytics viewer if data is provided.

    Args:
        ui_state: Current UI state
        analytics_data: Analytics data dictionary

    Returns:
        Updated UI state with analytics viewer shown (if data provided)
    """
    if analytics_data:
        return show_analytics_viewer(ui_state, analytics_data)
    return ui_state


def _refresh_ui_state_from_db(ui_state: UIState) -> UIState:
    """
    Refresh UI state from database.

    Updates shuffle mode and playlist info to reflect latest database state.

    Args:
        ui_state: Current UI state

    Returns:
        Updated UI state with fresh database values
    """
    try:
        from music_minion.domain.playback import state as playback_state
        from music_minion.domain.playlists import crud as playlists

        # Update shuffle mode
        shuffle_enabled = playback_state.get_shuffle_mode()
        ui_state = replace(ui_state, shuffle_enabled=shuffle_enabled)

        # Update playlist info
        active = playlists.get_active_playlist()
        if active:
            playlist_tracks = playlists.get_playlist_tracks(active['id'])
            position_info = playback_state.get_playlist_position(active['id'])

            playlist_info = PlaylistInfo(
                id=active['id'],
                name=active['name'],
                type=active['type'],
                track_count=len(playlist_tracks),
                current_position=position_info[1] if position_info else None
            )
            ui_state = replace(ui_state, playlist_info=playlist_info)
        else:
            # No active playlist
            ui_state = replace(ui_state, playlist_info=PlaylistInfo())

    except Exception:
        # Silently ignore errors - don't break UI on refresh failure
        pass

    return ui_state


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


def _handle_internal_command(ctx: AppContext, ui_state: UIState, cmd: InternalCommand) -> tuple[AppContext, UIState, bool]:
    """
    Handle type-safe internal commands from UI.

    Args:
        ctx: Application context
        ui_state: UI state
        cmd: Internal command with action and data

    Returns:
        Tuple of (updated AppContext, updated UIState, should_quit)
    """
    if cmd.action == 'play_track_from_viewer':
        playlist_id = cmd.data.get('playlist_id')
        track_index = cmd.data.get('track_index')
        if playlist_id is not None and track_index is not None:
            ctx, ui_state = handle_play_track_from_viewer(ctx, ui_state, playlist_id, track_index)
        return ctx, ui_state, False

    elif cmd.action == 'remove_track_from_playlist':
        track_id = cmd.data.get('track_id')
        playlist_name = cmd.data.get('playlist_name')
        if track_id is not None and playlist_name:
            ctx, ui_state = handle_remove_track_from_playlist(ctx, ui_state, track_id, playlist_name)
        return ctx, ui_state, False

    elif cmd.action == 'delete_playlist':
        playlist_name = cmd.data.get('playlist_name')
        if playlist_name:
            ctx, ui_state = handle_playlist_deletion(ctx, ui_state, playlist_name)
        return ctx, ui_state, False

    elif cmd.action == 'review_input':
        # Handle review mode input
        user_input = cmd.data.get('input', '')
        if user_input:
            from music_minion.ui.blessed.events.review_handler import (
                handle_review_input, handle_review_confirmation
            )

            if ui_state.review_mode == 'conversation':
                ctx, ui_state = handle_review_input(ctx, ui_state, user_input)
            elif ui_state.review_mode == 'confirm':
                ctx, ui_state = handle_review_confirmation(ctx, ui_state, user_input)

        return ctx, ui_state, False

    elif cmd.action == 'show_analytics_viewer':
        # Show analytics viewer with data
        analytics_data = cmd.data.get('analytics_data', {})
        ui_state = _show_analytics_viewer_if_data(ui_state, analytics_data)
        return ctx, ui_state, False

    else:
        # Unknown command action, log it and continue
        ui_state = add_history_line(ui_state, f"⚠️ Unknown internal command: {cmd.action}", 'yellow')
        return ctx, ui_state, False


def execute_command(ctx: AppContext, ui_state: UIState, command_line: str | InternalCommand) -> tuple[AppContext, UIState, bool]:
    """
    Execute command and return updated state.

    Args:
        ctx: Application context
        ui_state: UI state
        command_line: Full command line string or InternalCommand

    Returns:
        Tuple of (updated AppContext, updated UIState, should_quit)
    """
    # Handle internal typed commands
    if isinstance(command_line, InternalCommand):
        return _handle_internal_command(ctx, ui_state, command_line)

    # Parse string command
    command, args = parse_command_line(command_line)

    if not command:
        return ctx, ui_state, False

    # Special case: QUIT signal from keyboard handler
    if command == 'QUIT':
        return ctx, ui_state, True

    # Special case: Playlist selection from palette
    if command == '__SELECT_PLAYLIST__':
        playlist_name = ' '.join(args)
        ctx, ui_state = handle_playlist_selection(ctx, ui_state, playlist_name)
        return ctx, ui_state, False

    # Special case: Save wizard playlist
    if command == '__SAVE_WIZARD_PLAYLIST__':
        ctx, ui_state = handle_wizard_save(ctx, ui_state)
        return ctx, ui_state, False

    # Add command to history display
    ui_state = add_history_line(ui_state, f"> {command_line}", 'cyan')

    # Add command to command history (for up/down arrow navigation)
    ui_state = add_command_to_history(ui_state, command_line)

    # Special handling for scan command - run in background
    if command == 'scan':
        from music_minion.commands import admin
        from music_minion.ui.blessed.state import start_scan

        # Start background scan
        admin.start_background_scan(ctx)

        # Initialize scan UI state (actual progress will be polled)
        ui_state = start_scan(ui_state, 0)
        ui_state = add_history_line(ui_state, "🔍 Starting library scan in background...", 'cyan')

        return ctx, ui_state, False

    # Buffer output
    output_buffer = io.StringIO()
    error_buffer = io.StringIO()

    # Execute command through router with captured output
    try:
        with redirect_stdout(output_buffer), redirect_stderr(error_buffer):
            from music_minion.router import handle_command
            ctx, should_continue = handle_command(ctx, command, args)

            if not should_continue:
                # Command requested exit (quit/exit command)
                return ctx, ui_state, True

    except Exception as e:
        # Add error to history
        ui_state = add_history_line(ui_state, f"❌ Error: {e}", 'red')
        return ctx, ui_state, False

    # Get captured output
    stdout_output = output_buffer.getvalue()
    stderr_output = error_buffer.getvalue()

    # Add output to history
    if stdout_output:
        for line in stdout_output.strip().split('\n'):
            ui_state = add_history_line(ui_state, line, 'white')

    if stderr_output:
        for line in stderr_output.strip().split('\n'):
            ui_state = add_history_line(ui_state, line, 'red')

    # Process any UI actions from context
    if ctx.ui_action:
        ctx, ui_state = _process_ui_action(ctx, ui_state)

    # Refresh UI state from database after command execution
    # This ensures shuffle mode, playlist info, etc. are up-to-date
    ui_state = _refresh_ui_state_from_db(ui_state)

    return ctx, ui_state, False


def _process_ui_action(ctx: AppContext, ui_state: UIState) -> tuple[AppContext, UIState]:
    """
    Process UI actions from context.

    Args:
        ctx: Application context with ui_action
        ui_state: Current UI state

    Returns:
        Tuple of (updated AppContext, updated UIState)
    """
    from music_minion.ui.blessed.components.palette import load_playlist_items
    from music_minion.ui.blessed.state import show_playlist_palette

    action = ctx.ui_action

    if action['type'] == 'show_playlist_palette':
        # Show playlist palette with loaded items
        items = load_playlist_items()
        ui_state = show_playlist_palette(ui_state, items)

    elif action['type'] == 'start_wizard':
        # Start wizard with given type and data
        wizard_type = action.get('wizard_type', '')
        wizard_data = action.get('wizard_data', {})
        ui_state = start_wizard(ui_state, wizard_type, wizard_data)

    elif action['type'] == 'show_track_viewer':
        # Show track viewer for playlist
        playlist_name = action.get('playlist_name', '')
        ctx, ui_state = handle_show_track_viewer(ctx, ui_state, playlist_name)

    elif action['type'] == 'start_review_mode':
        # Start AI review mode
        from music_minion.ui.blessed.state import start_review_mode
        track_data = action.get('track_data', {})
        tags_with_reasoning = action.get('tags_with_reasoning', {})
        ui_state = start_review_mode(ui_state, track_data, tags_with_reasoning)

    elif action['type'] == 'show_analytics_viewer':
        # Show analytics viewer with data
        analytics_data = action.get('analytics_data', {})
        ui_state = _show_analytics_viewer_if_data(ui_state, analytics_data)

    # Clear the ui_action after processing
    ctx = ctx.with_ui_action(None)

    return ctx, ui_state
