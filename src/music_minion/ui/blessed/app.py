"""Main event loop and entry point for blessed UI."""

import sys
from blessed import Terminal
from ...context import AppContext
from .state import UIState, update_track_info
from .components import (
    render_dashboard,
    render_history,
    render_input,
    render_palette,
    calculate_layout,
)
from .events.keyboard import handle_key
from .events.commands import execute_command


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
        if status.get('file'):
            # Get track from database
            db_track = database.get_track_by_path(status['file'])

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
                with database.get_db_connection() as conn:
                    tags = database.get_track_tags(conn, db_track['id'])
                    notes = database.get_track_notes(conn, db_track['id'])

                    track_data.update({
                        'tags': [t['tag'] for t in tags],
                        'notes': notes[0]['note'] if notes else '',
                        'rating': db_track.get('rating'),
                        'last_played': db_track.get('last_played'),
                        'play_count': db_track.get('play_count', 0),
                    })

                ui_state = update_track_info(ui_state, track_data)

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
    last_palette_state = (False, 0)
    layout = None

    while not should_quit:
        # Poll player state every 10 frames (~1 second at 0.1s timeout)
        should_poll = frame_count % 10 == 0
        if should_poll:
            ctx, ui_state = poll_player_state(ctx, ui_state)

        # Check if state changed (only redraw if needed)
        # Only compute hash when we polled or when other state changes might have occurred
        current_state_hash = None
        if should_poll or last_state_hash is None:
            current_state_hash = hash((
                ctx.player_state.current_track,
                ctx.player_state.is_playing,
                int(ctx.player_state.current_position),  # Floor to avoid constant changes
                ctx.player_state.duration,
                len(ui_state.history),
                ui_state.feedback_message,
            ))

        # Check for input-only changes (no full redraw needed)
        input_changed = ui_state.input_text != last_input_text
        palette_state_changed = (ui_state.palette_visible, ui_state.palette_selected) != last_palette_state

        # Determine if we need a full redraw
        needs_full_redraw = needs_full_redraw or (current_state_hash is not None and current_state_hash != last_state_hash)

        if needs_full_redraw:
            # Full screen redraw
            last_state_hash = current_state_hash
            needs_full_redraw = False

            # Clear screen
            print(term.clear)

            # Calculate layout
            layout = calculate_layout(term, ui_state)

            # Render all sections
            render_dashboard(
                term,
                ctx.player_state,
                ui_state,
                layout['dashboard_y']
            )

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

            if ui_state.palette_visible:
                render_palette(
                    term,
                    ui_state,
                    layout['palette_y'],
                    layout['palette_height']
                )

            # Flush output
            sys.stdout.flush()

            last_input_text = ui_state.input_text
            last_palette_state = (ui_state.palette_visible, ui_state.palette_selected)

        elif input_changed or palette_state_changed:
            # Partial update - only input and palette changed
            if layout:
                # If palette visibility changed, do a full redraw instead
                if palette_state_changed and ui_state.palette_visible != last_palette_state[0]:
                    needs_full_redraw = True
                else:
                    # Clear input area (3 lines: top border, input, bottom border)
                    input_y = layout['input_y']
                    for i in range(3):
                        sys.stdout.write(term.move_xy(0, input_y + i) + term.clear_eol)

                    # Clear palette area if visible
                    if ui_state.palette_visible:
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

                    if ui_state.palette_visible:
                        render_palette(
                            term,
                            ui_state,
                            layout['palette_y'],
                            layout['palette_height']
                        )

                    # Flush output
                    sys.stdout.flush()

                    last_input_text = ui_state.input_text
                    last_palette_state = (ui_state.palette_visible, ui_state.palette_selected)

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
