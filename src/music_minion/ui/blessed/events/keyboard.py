"""Keyboard event handling."""

from blessed.keyboard import Keystroke
from ..state import (
    UIState,
    append_input_char,
    delete_input_char,
    set_input_text,
    show_palette,
    hide_palette,
    move_palette_selection,
    update_palette_filter,
    clear_history,
    navigate_history_up,
    navigate_history_down,
    reset_history_navigation,
)
from ..styles.palette import filter_commands, COMMAND_DEFINITIONS


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
    elif key.name == 'KEY_DELETE':
        event['type'] = 'delete'
    elif key.name == 'KEY_UP':
        event['type'] = 'arrow_up'
    elif key.name == 'KEY_DOWN':
        event['type'] = 'arrow_down'
    elif key == '\x03':  # Ctrl+C
        event['type'] = 'ctrl_c'
    elif key == '\x0c':  # Ctrl+L
        event['type'] = 'ctrl_l'
    elif key and key.isprintable():
        event['type'] = 'char'

    return event


def handle_key(state: UIState, key: Keystroke, palette_height: int = 10) -> tuple[UIState, str | None]:
    """
    Handle keyboard input and return updated state.

    Args:
        state: Current UI state
        key: blessed Keystroke
        palette_height: Available height for palette (for scroll calculations)

    Returns:
        Tuple of (updated state, command to execute or None)
    """
    event = parse_key(key)
    command_to_execute = None

    # Handle Ctrl+C (quit)
    if event['type'] == 'ctrl_c':
        return state, 'QUIT'

    # Handle Ctrl+L (clear history)
    if event['type'] == 'ctrl_l':
        state = clear_history(state)
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
            # Remove "/" prefix for filtering
            query = state.input_text[1:] if state.input_text.startswith("/") else state.input_text
            filtered = filter_commands(query, COMMAND_DEFINITIONS)
            # Convert to format expected by state (category, cmd, icon, desc)
            state = update_palette_filter(state, query, filtered)

        return state, None

    # Handle delete (behaves like backspace since cursor is always at end)
    if event['type'] == 'delete':
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
                # Remove "/" prefix for filtering
                query = state.input_text[1:] if state.input_text.startswith("/") else state.input_text
                filtered = filter_commands(query, COMMAND_DEFINITIONS)
                state = update_palette_filter(state, query, filtered)

        return state, None

    return state, None
