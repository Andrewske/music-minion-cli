"""Wizard mode keyboard handlers."""

import uuid
from music_minion.ui.blessed.state import (
    UIState,
    cancel_wizard,
    update_wizard_step,
    update_wizard_data,
    clear_wizard_error,
    move_wizard_selection,
    append_input_char,
    delete_input_char,
)
from music_minion.ui.blessed.helpers.filter_input import get_value_options
from music_minion.domain.playlists import filters as playlist_filters
from music_minion.domain.playlists import crud as playlists


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
    current_step = state.wizard_step

    # Escape always cancels wizard
    if event["type"] == "escape":
        return cancel_wizard(state), None

    # Arrow key navigation (when options are available)
    if state.wizard_options:
        if event["type"] == "arrow_up":
            state = move_wizard_selection(state, -1)
            return state, None
        elif event["type"] == "arrow_down":
            state = move_wizard_selection(state, 1)
            return state, None

    # Backspace handling - only for value step (no options)
    if event["type"] == "backspace":
        if current_step == "value" and not state.wizard_options:
            state = delete_input_char(state)
            return state, None

    # Regular character input - only for value step (no options)
    if event["type"] == "char" and event["char"]:
        if current_step == "value" and not state.wizard_options:
            state = append_input_char(state, event["char"])
            # Clear error when user starts typing
            state = clear_wizard_error(state)
            return state, None

    # Enter key handling (step-specific)
    if event["type"] == "enter":
        # Handle preview step specially - return save command
        if current_step == "preview":
            return state, "__SAVE_WIZARD_PLAYLIST__"
        return handle_wizard_enter(state), None

    # Preview step: 'A' to add another filter
    if current_step == "preview" and event["char"] and event["char"].lower() == "a":
        # Add another filter - go back to field step with options
        field_options = sorted(list(playlist_filters.VALID_FIELDS))
        state = update_wizard_step(state, "field", field_options)
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

    if current_step == "field":
        # Use selected option
        if state.wizard_options and state.wizard_selected < len(state.wizard_options):
            selected_field = state.wizard_options[state.wizard_selected]
            # Don't mutate - pass update dict directly
            state = update_wizard_data(state, {"current_field": selected_field})

            # Determine operators for next step
            if selected_field in playlist_filters.NUMERIC_FIELDS:
                operator_options = sorted(list(playlist_filters.NUMERIC_OPERATORS))
            else:
                operator_options = sorted(list(playlist_filters.TEXT_OPERATORS))

            state = update_wizard_step(state, "operator", operator_options)
        return state

    elif current_step == "operator":
        # Use selected option
        if state.wizard_options and state.wizard_selected < len(state.wizard_options):
            selected_operator = state.wizard_options[state.wizard_selected]
            # Don't mutate - pass update dict directly
            state = update_wizard_data(state, {"current_operator": selected_operator})

            # Check if value step should have options (e.g., genre selection)
            field = state.wizard_data.get("current_field", "")
            display_options, raw_values = get_value_options(field, selected_operator)
            if display_options:
                # Use list selection for value step
                state = update_wizard_step(state, "value", options=display_options)
            else:
                # Value step has no options (free text input)
                state = update_wizard_step(state, "value", options=None)
        return state

    elif current_step == "value":
        # Value step: typed input or list selection
        if state.wizard_options:
            # List selection mode - use selected option
            if state.wizard_selected < len(state.wizard_options):
                selected_value = state.wizard_options[state.wizard_selected]
                # For genre selection, we need to map display option back to raw value
                field = state.wizard_data.get("current_field", "")
                operator = state.wizard_data.get("current_operator", "")
                _, raw_values = get_value_options(field, operator)
                if raw_values and state.wizard_selected < len(raw_values):
                    selected_value = raw_values[state.wizard_selected]

                state = update_wizard_data(state, {"current_value": selected_value})
        else:
            # Text input mode
            user_input = state.input_text.strip()
            if user_input:
                # Don't mutate - pass update dict directly
                state = update_wizard_data(state, {"current_value": user_input})

        # Check if we have a value set
        if state.wizard_data.get("current_value"):
            # Check if we have filters already (need conjunction) or go to preview
            filters = state.wizard_data.get("filters", [])
            if filters:
                # Need conjunction - show options
                conjunction_options = ["AND", "OR"]
                state = update_wizard_step(state, "conjunction", conjunction_options)
            else:
                # First filter - add it and go to preview
                state = add_current_filter_to_wizard(state, "AND")
                state = generate_preview_data(state)
                state = update_wizard_step(state, "preview", options=None)
        return state

    elif current_step == "conjunction":
        # Use selected option
        if state.wizard_options and state.wizard_selected < len(state.wizard_options):
            selected_conjunction = state.wizard_options[state.wizard_selected]
            state = add_current_filter_to_wizard(state, selected_conjunction)
            state = generate_preview_data(state)
            state = update_wizard_step(state, "preview", options=None)
        return state

    elif current_step == "preview":
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
    filters = list(wizard_data.get("filters", []))  # Create new list

    new_filter = {
        "field": wizard_data.get("current_field", ""),
        "operator": wizard_data.get("current_operator", ""),
        "value": wizard_data.get("current_value", ""),
        "conjunction": conjunction,
    }

    filters.append(new_filter)

    # Create new wizard_data dict without mutating original
    new_wizard_data = {**wizard_data, "filters": filters}

    # Remove current filter fields from new dict
    new_wizard_data.pop("current_field", None)
    new_wizard_data.pop("current_operator", None)
    new_wizard_data.pop("current_value", None)

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
    playlist_name = wizard_data.get("name", "")

    # Create temporary playlist to evaluate filters
    try:
        # Create playlist with unique temporary name to avoid collisions
        temp_name = f"{playlist_name}_temp_{uuid.uuid4().hex[:8]}"
        playlist_id = playlists.create_playlist(temp_name, "smart", description=None)

        # Add filters
        for f in wizard_data.get("filters", []):
            playlist_filters.add_filter(
                playlist_id,
                f["field"],
                f["operator"],
                f["value"],
                f.get("conjunction", "AND"),
            )

        # Evaluate filters
        matching_tracks = playlist_filters.evaluate_filters(playlist_id)

        # Delete temporary playlist
        playlists.delete_playlist(playlist_id)

        # Store preview data
        wizard_data["matching_count"] = len(matching_tracks)
        wizard_data["preview_tracks"] = matching_tracks[:5]  # First 5 tracks

    except Exception:
        # On error, set empty preview
        wizard_data["matching_count"] = 0
        wizard_data["preview_tracks"] = []

    return update_wizard_data(state, wizard_data)
