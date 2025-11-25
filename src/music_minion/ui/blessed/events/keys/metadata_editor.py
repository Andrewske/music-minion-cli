"""Metadata editor mode keyboard handlers."""

from music_minion.ui.blessed.state import (
    UIState,
    InternalCommand,
    save_field_edit,
    cancel_field_edit,
    save_add_item,
    cancel_add_item,
    replace,
)
from music_minion.ui.blessed.events.commands.metadata_handlers import (
    handle_metadata_editor_navigation,
    handle_metadata_editor_back,
)


def handle_metadata_editor_key(
    state: UIState, event: dict
) -> tuple[UIState | None, str | InternalCommand | None]:
    """
    Handle keyboard events for metadata editor mode.

    Args:
        state: Current UI state (metadata editor must be visible)
        event: Parsed key event from parse_key()

    Returns:
        Tuple of (updated state or None if not handled, command to execute or None)
    """
    # Special handling for editing_field mode
    if state.editor_mode == "editing_field":
        # Escape cancels editing
        if event["type"] == "escape":
            state = cancel_field_edit(state)
            return state, None

        # Enter saves field
        if event["type"] == "enter":
            state = save_field_edit(state)
            return state, None

        # Backspace deletes character
        if event["type"] == "backspace":
            if state.editor_input:
                new_input = state.editor_input[:-1]
                state = replace(state, editor_input=new_input)
            return state, None

        # Regular character: append to input
        if event["type"] == "char" and event["char"]:
            new_input = state.editor_input + event["char"]
            state = replace(state, editor_input=new_input)
            return state, None

        # Consume any other key in editing mode
        return state, None

    # Special handling for adding_item mode
    if state.editor_mode == "adding_item":
        # Escape cancels adding
        if event["type"] == "escape":
            state = cancel_add_item(state)
            return state, None

        # Enter saves new item
        if event["type"] == "enter":
            state = save_add_item(state)
            return state, None

        # Backspace deletes character
        if event["type"] == "backspace":
            if state.editor_input:
                new_input = state.editor_input[:-1]
                state = replace(state, editor_input=new_input)
            return state, None

        # Regular character: append to input
        if event["type"] == "char" and event["char"]:
            new_input = state.editor_input + event["char"]
            state = replace(state, editor_input=new_input)
            return state, None

        # Consume any other key in adding mode
        return state, None

    # Main editor and list editor modes
    # Escape closes editor with save
    if event["type"] == "escape":
        # Use internal command to trigger save
        return state, InternalCommand(action="metadata_save")

    # Arrow keys / j/k for navigation
    if event["type"] == "arrow_up" or (event["char"] and event["char"] == "k"):
        state = handle_metadata_editor_navigation(state, -1)
        return state, None

    if event["type"] == "arrow_down" or (event["char"] and event["char"] == "j"):
        state = handle_metadata_editor_navigation(state, 1)
        return state, None

    # Enter - edit selected field
    if event["type"] == "enter":
        return state, InternalCommand(action="metadata_edit")

    # Delete - delete item (list editor only)
    if event["type"] == "delete" or (event["char"] and event["char"] == "d"):
        return state, InternalCommand(action="metadata_delete")

    # 'a' - add item (list editor only)
    if event["char"] and event["char"] == "a":
        return state, InternalCommand(action="metadata_add")

    # 'q' - back to main editor (from list editor)
    if event["char"] and event["char"] == "q":
        state = handle_metadata_editor_back(state)
        return state, None

    # For any other key in metadata editor mode, consume it and do nothing
    return state, None
