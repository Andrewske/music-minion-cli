"""Main event loop and entry point for blessed UI."""

import sys
from pathlib import Path
from blessed import Terminal
from music_minion.context import AppContext
from .state import UIState, update_track_info
from .components import (
    render_dashboard,
    render_history,
    render_input,
    render_palette,
    render_smart_playlist_wizard,
    calculate_layout,
)
from .events.keyboard import handle_key
from .events.commands import execute_command


def _check_and_reload_files() -> None:
    """Check for pending file changes and reload if needed."""
    # Import main module to access global file watcher
    from ... import main

    if main.file_watcher_handler:
        try:
            from ... import dev_reload

            ready_files = main.file_watcher_handler.check_pending_changes()
            for filepath in ready_files:
                success = dev_reload.reload_module(filepath)
                if success:
                    filename = Path(filepath).name
                    # Note: Can't use safe_print here as it would interfere with blessed UI
                    # Reload happens silently in blessed mode
        except Exception:
            # Silently ignore errors in hot-reload to not break UI
            pass


def poll_player_state(ctx: AppContext, ui_state: UIState) -> tuple[AppContext, UIState]:
    """
    Poll player state and update both AppContext and UI state.

    Args:
        ctx: Application context with player state
        ui_state: UI state with cached display data

    Returns:
        Tuple of (updated AppContext, updated UIState)
    """
    # Import modules (lazy import to avoid circular deps)
    from ...core import database
    from ...domain.playback import player

    # Get player status
    try:
        status = player.get_player_status(ctx.player_state)

        # Update player state in AppContext
        new_player_state = ctx.player_state._replace(
            current_track=status.get('file'),
            is_playing=status.get('playing', False),
            current_position=status.get('position', 0.0),
            duration=status.get('duration', 0.0),
        )
        ctx = ctx.with_player_state(new_player_state)

        # If we have a current track, fetch metadata for UI display
        current_file = status.get('file')
        if current_file:
            # Get track from database
            db_track = database.get_track_by_path(current_file)

            if db_track:
                # Build track data for UI display
                track_data = {
                    'title': db_track.get('title') or 'Unknown',
                    'artist': db_track.get('artist') or 'Unknown',
                    'album': db_track.get('album'),
                    'year': db_track.get('year'),
                    'genre': db_track.get('genre'),
                    'bpm': db_track.get('bpm'),
                    'key': db_track.get('key'),
                }

                # Get additional database info
                tags = database.get_track_tags(db_track['id'])
                notes = database.get_track_notes(db_track['id'])

                track_data.update({
                    'tags': [t['tag_name'] for t in tags],
                    'notes': notes[0]['note_text'] if notes else '',
                    'rating': db_track.get('rating'),
                    'last_played': db_track.get('last_played'),
                    'play_count': db_track.get('play_count', 0),
                })

                ui_state = update_track_info(ui_state, track_data)
            else:
                # Track not in database - clear metadata to show fallback
                from dataclasses import replace
                ui_state = replace(ui_state, track_metadata=None, track_db_info=None)
        else:
            # No track playing - clear metadata
            from dataclasses import replace
            ui_state = replace(ui_state, track_metadata=None, track_db_info=None)

    except (OSError, ConnectionError, IOError):
        # Expected errors - player not running, socket issues
        # Silently continue - UI will show "not playing"
        pass
    except (database.sqlite3.Error, KeyError, ValueError) as e:
        # Database or data errors - log to stderr but don't crash
        print(f"Warning: Error polling player state: {e}", file=sys.stderr)
    except Exception as e:
        # Unexpected errors - log for debugging
        print(f"Unexpected error polling player state: {type(e).__name__}: {e}", file=sys.stderr)

    return ctx, ui_state


def run_interactive_ui(ctx: AppContext) -> AppContext:
    """
    Run the main interactive UI event loop.

    Args:
        ctx: Application context with config, tracks, and player state

    Returns:
        Updated AppContext after UI session ends
    """
    term = Terminal()

    with term.fullscreen(), term.cbreak(), term.hidden_cursor():
        try:
            ctx = main_loop(term, ctx)
        except KeyboardInterrupt:
            # Clean exit on Ctrl+C
            pass

    return ctx


def main_loop(term: Terminal, ctx: AppContext) -> AppContext:
    """
    Main event loop - functional style.

    Args:
        term: blessed Terminal instance
        ctx: Application context

    Returns:
        Updated AppContext after loop exits
    """
    # Create initial UI state (UI-only, not application state)
    ui_state = UIState()
    should_quit = False
    frame_count = 0
    last_state_hash = None
    needs_full_redraw = True
    last_input_text = ""
    last_palette_state = (False, 0, False, False, 0)  # (visible, selected, confirmation_active, wizard_active, wizard_selected)
    layout = None
    last_position = None  # Track position separately for partial updates
    dashboard_line_mapping = {}  # Store line offsets from last full dashboard render
    last_dashboard_height = None  # Track dashboard height to avoid unnecessary clears

    while not should_quit:
        # Check for file changes if hot-reload is enabled
        _check_and_reload_files()

        # Poll player state every 10 frames (~1 second at 0.1s timeout)
        should_poll = frame_count % 10 == 0
        if should_poll:
            ctx, ui_state = poll_player_state(ctx, ui_state)

        # Check if state changed (only redraw if needed)
        # Only compute hash when we polled or when other state changes might have occurred
        current_state_hash = None
        if should_poll or last_state_hash is None:
            # Hash excludes current_position to avoid full redraws every second
            # Position is tracked separately for partial dashboard updates
            current_state_hash = hash((
                ctx.player_state.current_track,
                ctx.player_state.is_playing,
                ctx.player_state.duration,
                len(ui_state.history),
                ui_state.feedback_message,
            ))

        # Check for input-only changes (no full redraw needed)
        input_changed = ui_state.input_text != last_input_text
        palette_state_changed = (ui_state.palette_visible, ui_state.palette_selected, ui_state.confirmation_active, ui_state.wizard_active, ui_state.wizard_selected) != last_palette_state

        # Determine if we need a full redraw
        needs_full_redraw = needs_full_redraw or (current_state_hash is not None and current_state_hash != last_state_hash)

        if needs_full_redraw:
            # Render dashboard first to check if height changed
            dashboard_height, dashboard_line_mapping = render_dashboard(
                term,
                ctx.player_state,
                ui_state,
                0  # Dashboard always starts at y=0
            )

            # Only clear screen if dashboard height changed (or first render)
            height_changed = last_dashboard_height != dashboard_height
            if height_changed or last_dashboard_height is None:
                # Clear screen and re-render everything
                print(term.clear)

                # Re-render dashboard after clear
                dashboard_height, dashboard_line_mapping = render_dashboard(
                    term,
                    ctx.player_state,
                    ui_state,
                    0
                )

            # Update tracking variables
            last_state_hash = current_state_hash
            needs_full_redraw = False
            last_dashboard_height = dashboard_height

            # Calculate layout with actual dashboard height
            layout = calculate_layout(term, ui_state, dashboard_height)

            # Render remaining sections
            render_history(
                term,
                ui_state,
                layout['history_y'],
                layout['history_height']
            )

            render_input(
                term,
                ui_state,
                layout['input_y']
            )

            # Render palette OR wizard (mutually exclusive)
            if ui_state.wizard_active:
                render_smart_playlist_wizard(
                    term,
                    ui_state,
                    layout['palette_y'],
                    layout['palette_height']
                )
            elif ui_state.palette_visible:
                render_palette(
                    term,
                    ui_state,
                    layout['palette_y'],
                    layout['palette_height']
                )

            # Flush output
            sys.stdout.flush()

            last_input_text = ui_state.input_text
            last_palette_state = (ui_state.palette_visible, ui_state.palette_selected, ui_state.confirmation_active, ui_state.wizard_active, ui_state.wizard_selected)
            last_position = int(ctx.player_state.current_position)  # Update position after full redraw

        elif input_changed or palette_state_changed:
            # Partial update - only input and palette changed
            if layout:
                # If palette or wizard visibility changed, do a full redraw instead
                if palette_state_changed and (ui_state.palette_visible != last_palette_state[0] or ui_state.wizard_active != last_palette_state[3]):
                    needs_full_redraw = True
                else:
                    # Clear input area (3 lines: top border, input, bottom border)
                    input_y = layout['input_y']
                    for i in range(3):
                        sys.stdout.write(term.move_xy(0, input_y + i) + term.clear_eol)

                    # Clear palette/wizard area if visible
                    if ui_state.palette_visible or ui_state.wizard_active:
                        palette_y = layout['palette_y']
                        palette_height = layout['palette_height']
                        for i in range(palette_height):
                            sys.stdout.write(term.move_xy(0, palette_y + i) + term.clear_eol)

                    # Re-render
                    render_input(
                        term,
                        ui_state,
                        layout['input_y']
                    )

                    # Render palette OR wizard (mutually exclusive)
                    if ui_state.wizard_active:
                        render_smart_playlist_wizard(
                            term,
                            ui_state,
                            layout['palette_y'],
                            layout['palette_height']
                        )
                    elif ui_state.palette_visible:
                        render_palette(
                            term,
                            ui_state,
                            layout['palette_y'],
                            layout['palette_height']
                        )

                    # Flush output
                    sys.stdout.flush()

                    last_input_text = ui_state.input_text
                    last_palette_state = (ui_state.palette_visible, ui_state.palette_selected, ui_state.confirmation_active, ui_state.wizard_active, ui_state.wizard_selected)

        else:
            # Check if only position changed (partial dashboard update)
            current_position = int(ctx.player_state.current_position)
            position_changed = last_position != current_position

            if position_changed and layout and ctx.player_state.is_playing and dashboard_line_mapping:
                # Partial update - only update time-sensitive dashboard elements
                # This avoids full screen clear and only updates specific lines
                from .components.dashboard import render_dashboard_partial

                render_dashboard_partial(
                    term,
                    ctx.player_state,
                    ui_state,
                    layout['dashboard_y'],
                    dashboard_line_mapping
                )

                sys.stdout.flush()
                last_position = current_position

        # Wait for input (with timeout for background updates)
        key = term.inkey(timeout=0.1)

        if key:
            # Handle keyboard input
            palette_height = layout['palette_height'] if layout else 10
            ui_state, command_line = handle_key(ui_state, key, palette_height)

            # Execute command if one was triggered
            if command_line:
                ctx, ui_state, should_quit = execute_command(ctx, ui_state, command_line)
                # Full redraw after command execution
                needs_full_redraw = True

        frame_count += 1

    return ctx
