"""Main event loop and entry point for blessed UI."""

import sys
from typing import Any
from blessed import Terminal
from .state import UIState, create_initial_state, update_player_state, update_track_info
from .rendering import (
    render_dashboard,
    render_history,
    render_input,
    render_palette,
    calculate_layout,
)
from .events.keyboard import handle_key
from .events.commands import execute_command


def poll_player_state(state: UIState, player_state: Any) -> UIState:
    """
    Poll player state and update UI state.

    Args:
        state: Current UI state
        player_state: Player state from main module

    Returns:
        Updated UI state with latest player data
    """
    # Import player module (lazy import to avoid circular deps)
    from music_minion import player, database, library

    # Get player status
    try:
        status = player.get_player_status(player_state)

        # Update player state in UI
        player_data = {
            'current_track': status.get('file'),
            'is_playing': status.get('playing', False),
            'is_paused': not status.get('playing', False) if status.get('file') else False,
            'current_position': status.get('position', 0.0),
            'duration': status.get('duration', 0.0),
        }
        state = update_player_state(state, player_data)

        # If we have a current track, fetch metadata
        if status.get('file'):
            # Get track from library
            track = library.get_track_by_path(state.music_tracks, status['file'])

            if track:
                # Get metadata from file
                track_data = {
                    'title': track.title or 'Unknown',
                    'artist': track.artist or 'Unknown',
                    'album': track.album,
                    'year': track.year,
                    'genre': track.genre,
                    'bpm': track.bpm,
                    'key': track.key,
                }

                # Get database info
                with database.get_db_connection() as conn:
                    db_track = database.get_track_by_path(conn, status['file'])
                    if db_track:
                        tags = database.get_track_tags(conn, db_track['id'])
                        notes = database.get_track_notes(conn, db_track['id'])
                        rating = db_track.get('rating')
                        last_played = db_track.get('last_played')
                        play_count = db_track.get('play_count', 0)

                        track_data.update({
                            'tags': [t['tag'] for t in tags],
                            'notes': notes[0]['note'] if notes else '',
                            'rating': rating,
                            'last_played': last_played,
                            'play_count': play_count,
                        })

                state = update_track_info(state, track_data)

    except Exception as e:
        # Don't crash on polling errors
        pass

    return state


def run_interactive_ui(initial_state: UIState, player_state: Any = None) -> None:
    """
    Run the main interactive UI event loop.

    Args:
        initial_state: Initial UI state
        player_state: Player state from main module (optional)
    """
    term = Terminal()

    with term.fullscreen(), term.cbreak(), term.hidden_cursor():
        try:
            main_loop(term, initial_state, player_state)
        except KeyboardInterrupt:
            # Clean exit on Ctrl+C
            pass


def main_loop(term: Terminal, state: UIState, player_state: Any = None) -> None:
    """
    Main event loop - functional style.

    Args:
        term: blessed Terminal instance
        state: Initial UI state
        player_state: Player state from main module (optional)
    """
    should_quit = False
    frame_count = 0

    while not should_quit:
        # Poll player state every 10 frames (~1 second at 0.1s timeout)
        if player_state and frame_count % 10 == 0:
            state = poll_player_state(state, player_state)

        # Clear screen
        print(term.clear)

        # Calculate layout
        layout = calculate_layout(term, state)

        # Render all sections
        dashboard_height = render_dashboard(
            term,
            state,
            layout['dashboard_y']
        )

        render_history(
            term,
            state,
            layout['history_y'],
            layout['history_height']
        )

        render_input(
            term,
            state,
            layout['input_y']
        )

        if state.palette_visible:
            render_palette(
                term,
                state,
                layout['palette_y'],
                layout['palette_height']
            )

        # Flush output
        sys.stdout.flush()

        # Wait for input (with timeout for background updates)
        key = term.inkey(timeout=0.1)

        if key:
            # Handle keyboard input
            state, command_line = handle_key(state, key)

            # Execute command if one was triggered
            if command_line:
                state, should_quit = execute_command(state, command_line)

        frame_count += 1
