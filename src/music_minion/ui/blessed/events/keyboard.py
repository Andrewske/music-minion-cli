"""Keyboard event handling for wizard and normal input modes.

This module handles all keyboard input for the blessed UI, including:
- Wizard mode navigation and validation
- Command palette interaction
- History navigation (up/down arrows)
- Confirmation dialogs
- Normal command input

Key Functions:
    - handle_key: Main keyboard dispatcher
    - handle_wizard_key: Wizard-specific keyboard handling
    - handle_wizard_enter: Process Enter key in wizard mode
"""

import uuid
from blessed.keyboard import Keystroke
from ..state import (
    UIState,
    InternalCommand,
    append_input_char,
    delete_input_char,
    set_input_text,
    show_palette,
    hide_palette,
    move_palette_selection,
    update_palette_filter,
    clear_history,
    scroll_history_up,
    scroll_history_down,
    scroll_history_to_top,
    scroll_history_to_bottom,
    navigate_history_up,
    navigate_history_down,
    reset_history_navigation,
    show_confirmation,
    hide_confirmation,
    cancel_wizard,
    update_wizard_step,
    update_wizard_data,
    set_wizard_error,
    clear_wizard_error,
    move_wizard_selection,
    hide_track_viewer,
    move_track_viewer_selection,
    hide_analytics_viewer,
    scroll_analytics_viewer,
)
from ..styles.palette import filter_commands, COMMAND_DEFINITIONS
from ..components.track_viewer import TRACK_VIEWER_HEADER_LINES, TRACK_VIEWER_FOOTER_LINES
from music_minion.domain.playlists import filters as playlist_filters
from music_minion.domain.playlists import crud as playlists


def parse_key(key: Keystroke) -> dict:
    """
    Parse keystroke into event dictionary.

    Args:
        key: blessed Keystroke

    Returns:
        Event dictionary describing the key press
    """
    event = {
        'type': 'unknown',
        'key': key,
        'name': key.name if hasattr(key, 'name') else None,
        'char': str(key) if key and key.isprintable() else None,
    }

    # Identify key type
    if key.name == 'KEY_ENTER':
        event['type'] = 'enter'
    elif key.name == 'KEY_ESCAPE':
        event['type'] = 'escape'
    elif key.name == 'KEY_BACKSPACE' or key == '\x7f':
        event['type'] = 'backspace'
    elif key.name == 'KEY_DELETE' or str(key) == '\x1b[3~':
        event['type'] = 'delete'
    elif key.name == 'KEY_UP':
        event['type'] = 'arrow_up'
    elif key.name == 'KEY_DOWN':
        event['type'] = 'arrow_down'
    elif key.name == 'KEY_PGUP':  # Page Up (blessed uses PGUP not PPAGE)
        event['type'] = 'page_up'
    elif key.name == 'KEY_PGDOWN':  # Page Down (blessed uses PGDOWN not NPAGE)
        event['type'] = 'page_down'
    elif key.name == 'KEY_HOME':
        event['type'] = 'home'
    elif key.name == 'KEY_END':
        event['type'] = 'end'
    elif key == '\x03':  # Ctrl+C
        event['type'] = 'ctrl_c'
    elif key == '\x0c':  # Ctrl+L
        event['type'] = 'ctrl_l'
    elif key == '\x15':  # Ctrl+U (half page up - vim style)
        event['type'] = 'page_up'
    elif key == '\x04':  # Ctrl+D (half page down - vim style)
        event['type'] = 'page_down'
    elif key and key.isprintable():
        event['type'] = 'char'

    return event


def handle_wizard_key(state: UIState, event: dict) -> tuple[UIState | None, str | None]:
    """
    Handle keyboard events for wizard mode.

    Processes wizard-specific keyboard input:
    - Escape: Cancel wizard and exit
    - Arrow Up/Down: Navigate options (when options available)
    - Backspace: Delete character from input (value step only)
    - Char: Append character to input (value step only, or to filter options)
    - Enter: Accept selected option or validate input
    - 'A' in preview: Add another filter

    Returns None if key wasn't handled (falls through to normal handling).

    Args:
        state: Current UI state (wizard must be active)
        event: Parsed key event from parse_key()

    Returns:
        Tuple of (updated state or None if not handled, command to execute or None)
        Special commands: '__SAVE_WIZARD_PLAYLIST__' triggers save
    """
    wizard_data = state.wizard_data
    current_step = state.wizard_step

    # Escape always cancels wizard
    if event['type'] == 'escape':
        return cancel_wizard(state), None

    # Arrow key navigation (when options are available)
    if state.wizard_options:
        if event['type'] == 'arrow_up':
            state = move_wizard_selection(state, -1)
            return state, None
        elif event['type'] == 'arrow_down':
            state = move_wizard_selection(state, 1)
            return state, None

    # Backspace handling - only for value step (no options)
    if event['type'] == 'backspace':
        if current_step == 'value' and not state.wizard_options:
            state = delete_input_char(state)
            return state, None

    # Regular character input - only for value step (no options)
    if event['type'] == 'char' and event['char']:
        if current_step == 'value' and not state.wizard_options:
            state = append_input_char(state, event['char'])
            # Clear error when user starts typing
            state = clear_wizard_error(state)
            return state, None

    # Enter key handling (step-specific)
    if event['type'] == 'enter':
        # Handle preview step specially - return save command
        if current_step == 'preview':
            return state, '__SAVE_WIZARD_PLAYLIST__'
        return handle_wizard_enter(state), None

    # Preview step: 'A' to add another filter
    if current_step == 'preview' and event['char'] and event['char'].lower() == 'a':
        # Add another filter - go back to field step with options
        field_options = sorted(list(playlist_filters.VALID_FIELDS))
        state = update_wizard_step(state, 'field', field_options)
        return state, None

    # For any other key in wizard mode, consume it and do nothing
    # This prevents fallthrough to normal key handling
    return state, None


def handle_wizard_enter(state: UIState) -> UIState:
    """
    Handle Enter key in wizard based on current step.

    When options are available (field, operator, conjunction), uses the selected option.
    When no options (value), validates typed input.

    Validation rules:
    - field: Must be in VALID_FIELDS (selected from list)
    - operator: Must match field type (selected from list)
    - value: Any non-empty string (typed input)
    - conjunction: Must be 'AND' or 'OR' (selected from list)
    - preview: Triggers save command

    Args:
        state: Current UI state with wizard active

    Returns:
        Updated state with validation applied or step advanced
    """
    current_step = state.wizard_step

    if current_step == 'field':
        # Use selected option
        if state.wizard_options and state.wizard_selected < len(state.wizard_options):
            selected_field = state.wizard_options[state.wizard_selected]
            # Don't mutate - pass update dict directly
            state = update_wizard_data(state, {'current_field': selected_field})

            # Determine operators for next step
            if selected_field in playlist_filters.NUMERIC_FIELDS:
                operator_options = sorted(list(playlist_filters.NUMERIC_OPERATORS))
            else:
                operator_options = sorted(list(playlist_filters.TEXT_OPERATORS))

            state = update_wizard_step(state, 'operator', operator_options)
        return state

    elif current_step == 'operator':
        # Use selected option
        if state.wizard_options and state.wizard_selected < len(state.wizard_options):
            selected_operator = state.wizard_options[state.wizard_selected]
            # Don't mutate - pass update dict directly
            state = update_wizard_data(state, {'current_operator': selected_operator})
            # Value step has no options (free text input)
            state = update_wizard_step(state, 'value', options=None)
        return state

    elif current_step == 'value':
        # Value step: typed input (no options)
        user_input = state.input_text.strip()
        if user_input:
            # Don't mutate - pass update dict directly
            state = update_wizard_data(state, {'current_value': user_input})

            # Check if we have filters already (need conjunction) or go to preview
            filters = state.wizard_data.get('filters', [])
            if filters:
                # Need conjunction - show options
                conjunction_options = ['AND', 'OR']
                state = update_wizard_step(state, 'conjunction', conjunction_options)
            else:
                # First filter - add it and go to preview
                state = add_current_filter_to_wizard(state, 'AND')
                state = generate_preview_data(state)
                state = update_wizard_step(state, 'preview', options=None)
        return state

    elif current_step == 'conjunction':
        # Use selected option
        if state.wizard_options and state.wizard_selected < len(state.wizard_options):
            selected_conjunction = state.wizard_options[state.wizard_selected]
            state = add_current_filter_to_wizard(state, selected_conjunction)
            state = generate_preview_data(state)
            state = update_wizard_step(state, 'preview', options=None)
        return state

    elif current_step == 'preview':
        # Save playlist - return command to execute
        return state  # Command will be handled by caller

    return state


def add_current_filter_to_wizard(state: UIState, conjunction: str) -> UIState:
    """
    Add current filter data to wizard filters list.

    Args:
        state: Current UI state
        conjunction: 'AND' or 'OR'

    Returns:
        Updated state with filter added
    """
    wizard_data = state.wizard_data
    filters = list(wizard_data.get('filters', []))  # Create new list

    new_filter = {
        'field': wizard_data.get('current_field', ''),
        'operator': wizard_data.get('current_operator', ''),
        'value': wizard_data.get('current_value', ''),
        'conjunction': conjunction
    }

    filters.append(new_filter)

    # Create new wizard_data dict without mutating original
    new_wizard_data = {
        **wizard_data,
        'filters': filters
    }

    # Remove current filter fields from new dict
    new_wizard_data.pop('current_field', None)
    new_wizard_data.pop('current_operator', None)
    new_wizard_data.pop('current_value', None)

    return update_wizard_data(state, new_wizard_data)


def generate_preview_data(state: UIState) -> UIState:
    """
    Generate preview data (matching count and sample tracks).

    Creates a temporary playlist with the current filters to evaluate
    how many tracks match. Returns first 5 matching tracks for preview.

    Args:
        state: Current UI state with wizard active and filters defined

    Returns:
        Updated state with preview data (matching_count, preview_tracks)
    """
    wizard_data = state.wizard_data
    playlist_name = wizard_data.get('name', '')

    # Create temporary playlist to evaluate filters
    try:
        # Create playlist with unique temporary name to avoid collisions
        temp_name = f"{playlist_name}_temp_{uuid.uuid4().hex[:8]}"
        playlist_id = playlists.create_playlist(temp_name, 'smart', description=None)

        # Add filters
        for f in wizard_data.get('filters', []):
            playlist_filters.add_filter(
                playlist_id,
                f['field'],
                f['operator'],
                f['value'],
                f.get('conjunction', 'AND')
            )

        # Evaluate filters
        matching_tracks = playlist_filters.evaluate_filters(playlist_id)

        # Delete temporary playlist
        playlists.delete_playlist(playlist_id)

        # Store preview data
        wizard_data['matching_count'] = len(matching_tracks)
        wizard_data['preview_tracks'] = matching_tracks[:5]  # First 5 tracks

    except Exception:
        # On error, set empty preview
        wizard_data['matching_count'] = 0
        wizard_data['preview_tracks'] = []

    return update_wizard_data(state, wizard_data)



def handle_track_viewer_key(state: UIState, event: dict, viewer_height: int = 10) -> tuple[UIState | None, str | InternalCommand | None]:
    """
    Handle keyboard events for track viewer mode.

    Args:
        state: Current UI state (track viewer must be visible)
        event: Parsed key event from parse_key()
        viewer_height: Available height for viewer (for scroll calculations)

    Returns:
        Tuple of (updated state or None if not handled, command to execute or None)
    """
    # Escape closes viewer
    if event['type'] == 'escape':
        return hide_track_viewer(state), None

    # Calculate visible items (subtract header and footer lines)
    visible_items = max(1, viewer_height - TRACK_VIEWER_HEADER_LINES - TRACK_VIEWER_FOOTER_LINES)

    # Arrow key navigation
    if event['type'] == 'arrow_up':
        state = move_track_viewer_selection(state, -1, visible_items)
        return state, None

    if event['type'] == 'arrow_down':
        state = move_track_viewer_selection(state, 1, visible_items)
        return state, None

    # Enter plays selected track
    if event['type'] == 'enter':
        if state.track_viewer_selected < len(state.track_viewer_tracks):
            # Send typed command to play track from viewer
            command = InternalCommand(
                action='play_track_from_viewer',
                data={
                    'playlist_id': state.track_viewer_playlist_id,
                    'track_index': state.track_viewer_selected
                }
            )
            return state, command

    # Delete removes track from manual playlists
    if event['type'] == 'delete':
        if state.track_viewer_playlist_type == 'manual':
            if state.track_viewer_selected < len(state.track_viewer_tracks):
                selected_track = state.track_viewer_tracks[state.track_viewer_selected]
                track_id = selected_track['id']
                playlist_name = state.track_viewer_playlist_name

                # Show confirmation dialog
                state = show_confirmation(state, 'remove_track_from_playlist', {
                    'track_id': track_id,
                    'playlist_name': playlist_name,
                    'track_title': selected_track.get('title', 'Unknown'),
                    'track_artist': selected_track.get('artist', 'Unknown')
                })
                return state, None

    # For any other key in track viewer mode, consume it and do nothing
    return state, None


def handle_analytics_viewer_key(state: UIState, event: dict, viewer_height: int = 10) -> tuple[UIState | None, str | InternalCommand | None]:
    """
    Handle keyboard events for analytics viewer mode.

    Args:
        state: Current UI state (analytics viewer must be visible)
        event: Parsed key event from parse_key()
        viewer_height: Available height for viewer (for scroll calculations)

    Returns:
        Tuple of (updated state or None if not handled, command to execute or None)
    """
    # Escape or 'q' closes viewer
    if event['type'] == 'escape' or (event['char'] and event['char'].lower() == 'q'):
        return hide_analytics_viewer(state), None

    # Use pre-calculated line count (no need to re-format on every keystroke!)
    total_lines = state.analytics_viewer_total_lines
    max_scroll = max(0, total_lines - viewer_height + 1)  # +1 for footer

    # j or down arrow - scroll down
    if (event['char'] and event['char'].lower() == 'j') or event['type'] == 'arrow_down':
        state = scroll_analytics_viewer(state, delta=1, max_scroll=max_scroll)
        return state, None

    # k or up arrow - scroll up
    if (event['char'] and event['char'].lower() == 'k') or event['type'] == 'arrow_up':
        state = scroll_analytics_viewer(state, delta=-1, max_scroll=max_scroll)
        return state, None

    # Home - jump to top
    if event['type'] == 'home':
        state = scroll_analytics_viewer(state, delta=-999999, max_scroll=max_scroll)
        return state, None

    # End - jump to bottom
    if event['type'] == 'end':
        state = scroll_analytics_viewer(state, delta=999999, max_scroll=max_scroll)
        return state, None

    # For any other key in analytics viewer mode, consume it and do nothing
    return state, None


def handle_key(state: UIState, key: Keystroke, palette_height: int = 10, analytics_viewer_height: int = 30) -> tuple[UIState, str | InternalCommand | None]:
    """
    Handle keyboard input and return updated state.

    Args:
        state: Current UI state
        key: blessed Keystroke
        palette_height: Available height for palette (for scroll calculations)
        analytics_viewer_height: Available height for analytics viewer (for scroll calculations)

    Returns:
        Tuple of (updated state, command to execute or None)
    """
    event = parse_key(key)
    command_to_execute = None

    # Handle confirmation dialog keys (highest priority)
    if state.confirmation_active:
        if event['type'] == 'enter' or (event['char'] and event['char'].lower() == 'y'):
            # Confirmed (Enter defaults to Yes) - trigger action based on confirmation type
            if state.confirmation_type == 'delete_playlist':
                command_to_execute = InternalCommand(
                    action='delete_playlist',
                    data={'playlist_name': state.confirmation_data['playlist_name']}
                )
                state = hide_confirmation(state)
                return state, command_to_execute
            elif state.confirmation_type == 'remove_track_from_playlist':
                command_to_execute = InternalCommand(
                    action='remove_track_from_playlist',
                    data={
                        'track_id': state.confirmation_data['track_id'],
                        'playlist_name': state.confirmation_data['playlist_name']
                    }
                )
                state = hide_confirmation(state)
                return state, command_to_execute
        elif event['char'] and event['char'].lower() == 'n' or event['type'] == 'escape':
            # Cancelled
            state = hide_confirmation(state)
            return state, None
        # Ignore other keys during confirmation
        return state, None

    # Handle wizard keys (second priority after confirmation)
    if state.wizard_active:
        state_updated, cmd = handle_wizard_key(state, event)
        if state_updated is not None:
            return state_updated, cmd

    # Handle track viewer keys (third priority)
    if state.track_viewer_visible:
        state_updated, cmd = handle_track_viewer_key(state, event, palette_height)
        if state_updated is not None:
            return state_updated, cmd

    # Handle analytics viewer keys (fourth priority)
    if state.analytics_viewer_visible:
        state_updated, cmd = handle_analytics_viewer_key(state, event, analytics_viewer_height)
        if state_updated is not None:
            return state_updated, cmd

    # Handle review mode keys (fifth priority)
    if state.review_mode:
        # In review mode, Enter sends input to review handler
        if event['type'] == 'enter' and state.input_text.strip():
            # Return special command to trigger review handler
            user_input = state.input_text.strip()
            state = set_input_text(state, "")
            # Use InternalCommand to pass review input
            from music_minion.ui.blessed.state import InternalCommand
            return state, InternalCommand(action='review_input', data={'input': user_input})

    # Handle Ctrl+C (quit)
    if event['type'] == 'ctrl_c':
        return state, 'QUIT'

    # Handle Ctrl+L (clear history)
    if event['type'] == 'ctrl_l':
        state = clear_history(state)
        return state, None

    # Handle history scrolling (Ctrl+U/D, Home/End) - only when input is empty and no modal active
    # This allows scrolling through command history output (like analytics) without conflicting with typing
    if (not state.palette_visible and not state.wizard_active and
        not state.track_viewer_visible and not state.review_mode and
        not state.input_text):  # Only scroll when input is empty

        if event['type'] == 'page_up':
            # Scroll history up by ~visible height (Ctrl+U)
            state = scroll_history_up(state, lines=20)
            return state, None
        elif event['type'] == 'page_down':
            # Scroll history down by ~visible height (Ctrl+D)
            state = scroll_history_down(state, lines=20)
            return state, None
        elif event['type'] == 'home':
            # Jump to top of history (oldest messages)
            state = scroll_history_to_top(state)
            return state, None
        elif event['type'] == 'end':
            # Jump to bottom of history (newest messages)
            state = scroll_history_to_bottom(state)
            return state, None

    # Handle Escape (hide palette)
    if event['type'] == 'escape':
        if state.palette_visible:
            state = hide_palette(state)
        return state, None

    # Calculate visible items (subtract header and footer lines)
    visible_items = max(1, palette_height - 2)

    # Handle arrows - palette navigation OR command history navigation
    if event['type'] == 'arrow_up':
        if state.palette_visible:
            # Palette navigation with autofill
            state = move_palette_selection(state, -1, visible_items)
            # Autofill input with selected command
            if state.palette_items and state.palette_selected < len(state.palette_items):
                selected_cmd = state.palette_items[state.palette_selected][1]  # Command name
                state = set_input_text(state, selected_cmd)
        else:
            # Command history navigation (when palette not visible)
            state = navigate_history_up(state)
        return state, None

    if event['type'] == 'arrow_down':
        if state.palette_visible:
            # Palette navigation with autofill
            state = move_palette_selection(state, 1, visible_items)
            # Autofill input with selected command
            if state.palette_items and state.palette_selected < len(state.palette_items):
                selected_cmd = state.palette_items[state.palette_selected][1]  # Command name
                state = set_input_text(state, selected_cmd)
        else:
            # Command history navigation (when palette not visible)
            state = navigate_history_down(state)
        return state, None

    # Handle Enter (execute command or select palette item)
    if event['type'] == 'enter':
        if state.palette_visible and state.palette_items:
            # Select item from palette
            if state.palette_selected < len(state.palette_items):
                selected = state.palette_items[state.palette_selected]

                # Different handling based on palette mode
                if state.palette_mode == 'playlist':
                    # For playlist mode, send special command with playlist name
                    playlist_name = selected[1]  # Playlist name
                    command_to_execute = f"__SELECT_PLAYLIST__ {playlist_name}"
                else:
                    # For command mode, just use the command name
                    command_to_execute = selected[1]  # Command name

                state = hide_palette(state)
                state = set_input_text(state, "")
        else:
            # Execute typed command
            if state.input_text.strip():
                command_to_execute = state.input_text.strip()
                state = set_input_text(state, "")
        return state, command_to_execute

    # Handle backspace
    if event['type'] == 'backspace':
        state = delete_input_char(state)
        state = reset_history_navigation(state)

        # Update palette filter if visible
        if state.palette_visible:
            if state.palette_mode == 'playlist':
                # Filter playlists by name
                from ..components.palette import filter_playlist_items, load_playlist_items
                all_items = load_playlist_items()
                filtered = filter_playlist_items(state.input_text, all_items)
                state = update_palette_filter(state, state.input_text, filtered)
            else:
                # Filter commands
                query = state.input_text[1:] if state.input_text.startswith("/") else state.input_text
                filtered = filter_commands(query, COMMAND_DEFINITIONS)
                state = update_palette_filter(state, query, filtered)

        return state, None

    # Handle delete key
    if event['type'] == 'delete':
        # Check if in playlist palette mode - delete selected playlist
        if state.palette_visible and state.palette_mode == 'playlist':
            # Get selected playlist
            if state.palette_items and state.palette_selected < len(state.palette_items):
                selected = state.palette_items[state.palette_selected]
                playlist_name = selected[1]  # Playlist name

                # Show confirmation dialog
                state = show_confirmation(state, 'delete_playlist', {
                    'playlist_name': playlist_name
                })
            return state, None
        else:
            # Normal delete behavior (backspace)
            state = delete_input_char(state)
            state = reset_history_navigation(state)

            # Update palette filter if visible
            if state.palette_visible:
                # Remove "/" prefix for filtering
                query = state.input_text[1:] if state.input_text.startswith("/") else state.input_text
                filtered = filter_commands(query, COMMAND_DEFINITIONS)
                # Convert to format expected by state (category, cmd, icon, desc)
                state = update_palette_filter(state, query, filtered)

            return state, None

    # Handle regular characters
    if event['type'] == 'char' and event['char']:
        char = event['char']

        # Reset history navigation when typing
        state = reset_history_navigation(state)

        # Check if space closes palette after selection
        if char == ' ' and state.palette_visible and state.input_text:
            state = hide_palette(state)
            state = append_input_char(state, char)
            return state, None

        # Check if "/" triggers palette
        if char == '/' and not state.input_text:
            state = append_input_char(state, char)
            # Show palette with all commands
            filtered = filter_commands("", COMMAND_DEFINITIONS)
            state = update_palette_filter(state, "", filtered)
            state = show_palette(state)
        else:
            state = append_input_char(state, char)

            # Update palette filter if visible
            if state.palette_visible:
                if state.palette_mode == 'playlist':
                    # Filter playlists by name
                    from ..components.palette import filter_playlist_items, load_playlist_items
                    all_items = load_playlist_items()
                    filtered = filter_playlist_items(state.input_text, all_items)
                    state = update_palette_filter(state, state.input_text, filtered)
                else:
                    # Filter commands
                    query = state.input_text[1:] if state.input_text.startswith("/") else state.input_text
                    filtered = filter_commands(query, COMMAND_DEFINITIONS)
                    state = update_palette_filter(state, query, filtered)

        return state, None

    return state, None
