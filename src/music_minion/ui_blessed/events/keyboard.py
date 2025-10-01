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
)
from ..data.palette import filter_commands, COMMAND_DEFINITIONS


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


def handle_key(state: UIState, key: Keystroke) -> tuple[UIState, str | None]:
    """
    Handle keyboard input and return updated state.

    Args:
        state: Current UI state
        key: blessed Keystroke

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

    # Handle arrows (palette navigation)
    if event['type'] == 'arrow_up' and state.palette_visible:
        state = move_palette_selection(state, -1)
        return state, None

    if event['type'] == 'arrow_down' and state.palette_visible:
        state = move_palette_selection(state, 1)
        return state, None

    # Handle Enter (execute command or select palette item)
    if event['type'] == 'enter':
        if state.palette_visible and state.palette_items:
            # Select item from palette
            if state.palette_selected < len(state.palette_items):
                selected = state.palette_items[state.palette_selected]
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
