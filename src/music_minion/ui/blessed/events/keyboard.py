"""Keyboard event handling for wizard and normal input modes.

This module handles all keyboard input for the blessed UI, including:
- Wizard mode navigation and validation
- Command palette interaction
- History navigation (up/down arrows)
- Confirmation dialogs
- Comparison mode (Elo rating)
- Normal command input

Key Functions:
    - handle_key: Main keyboard dispatcher
    - handle_wizard_key: Wizard-specific keyboard handling
    - handle_wizard_enter: Process Enter key in wizard mode
    - handle_comparison_key: Comparison mode keyboard handling
"""

import uuid
import dataclasses
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
    hide_rating_history,
    move_rating_history_selection,
    delete_rating_history_item,
    hide_comparison_history,
    move_comparison_history_selection,
    hide_analytics_viewer,
    scroll_analytics_viewer,
    update_search_query,
    move_search_selection,
    set_search_mode,
    move_detail_selection,
    scroll_search_detail,
)
from ..styles.palette import filter_commands, COMMAND_DEFINITIONS
from ..components.track_viewer import (
    TRACK_VIEWER_HEADER_LINES,
    TRACK_VIEWER_FOOTER_LINES,
)
from music_minion.domain.playlists import filters as playlist_filters
from music_minion.domain.playlists import crud as playlists
from music_minion.domain.rating.elo import update_ratings, get_k_factor, select_strategic_pair
from music_minion.domain.rating.database import (
    get_or_create_rating,
    record_comparison,
    get_ratings_coverage,
)
from music_minion.core.output import log


def parse_key(key: Keystroke) -> dict:
    """
    Parse keystroke into event dictionary.

    Args:
        key: blessed Keystroke

    Returns:
        Event dictionary describing the key press
    """
    event = {
        "type": "unknown",
        "key": key,
        "name": key.name if hasattr(key, "name") else None,
        "char": str(key) if key and key.isprintable() else None,
    }

    # Identify key type
    if key.name == "KEY_ENTER":
        event["type"] = "enter"
    elif key.name == "KEY_ESCAPE":
        event["type"] = "escape"
    elif key.name == "KEY_BACKSPACE" or key == "\x7f":
        event["type"] = "backspace"
    elif key.name == "KEY_DELETE" or str(key) == "\x1b[3~":
        event["type"] = "delete"
    elif key.name == "KEY_UP":
        event["type"] = "arrow_up"
    elif key.name == "KEY_DOWN":
        event["type"] = "arrow_down"
    elif key.name == "KEY_LEFT":
        event["type"] = "arrow_left"
    elif key.name == "KEY_RIGHT":
        event["type"] = "arrow_right"
    elif key.name == "KEY_SLEFT":  # Shift+Left
        event["type"] = "shift_arrow_left"
    elif key.name == "KEY_SRIGHT":  # Shift+Right
        event["type"] = "shift_arrow_right"
    elif key.name == "KEY_PGUP":  # Page Up (blessed uses PGUP not PPAGE)
        event["type"] = "page_up"
    elif key.name == "KEY_PGDOWN":  # Page Down (blessed uses PGDOWN not NPAGE)
        event["type"] = "page_down"
    elif key.name == "KEY_HOME":
        event["type"] = "home"
    elif key.name == "KEY_END":
        event["type"] = "end"
    elif key == "\x03":  # Ctrl+C
        event["type"] = "ctrl_c"
    elif key == "\x0c":  # Ctrl+L
        event["type"] = "ctrl_l"
    elif key == "\x15":  # Ctrl+U (half page up - vim style)
        event["type"] = "page_up"
    elif key == "\x04":  # Ctrl+D (half page down - vim style)
        event["type"] = "page_down"
    elif key and key.isprintable():
        event["type"] = "char"

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
            # Value step has no options (free text input)
            state = update_wizard_step(state, "value", options=None)
        return state

    elif current_step == "value":
        # Value step: typed input (no options)
        user_input = state.input_text.strip()
        if user_input:
            # Don't mutate - pass update dict directly
            state = update_wizard_data(state, {"current_value": user_input})

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


def handle_track_viewer_key(
    state: UIState, event: dict, viewer_height: int = 10
) -> tuple[UIState | None, str | InternalCommand | None]:
    """
    Handle keyboard events for track viewer mode (2-mode: list/detail with filtering).

    Args:
        state: Current UI state (track viewer must be visible)
        event: Parsed key event from parse_key()
        viewer_height: Available height for viewer (for scroll calculations)

    Returns:
        Tuple of (updated state or None if not handled, command to execute or None)
    """
    from ..state import (
        set_track_viewer_mode,
        move_track_viewer_action_selection,
        update_track_viewer_filter,
    )

    # Escape - navigate back, clear filter, or close
    if event["type"] == "escape":
        if state.track_viewer_mode == "detail":
            # Detail -> List
            state = set_track_viewer_mode(state, "list")
            return state, None
        elif state.track_viewer_filter_query:
            # List with filter -> Clear filter
            state = update_track_viewer_filter(state, "", state.track_viewer_tracks)
            return state, None
        else:
            # List without filter -> Close
            return hide_track_viewer(state), None

    # 'q' key - close viewer (only in list mode)
    if event["type"] == "char" and event["char"] == "q":
        if state.track_viewer_mode == "list":
            return hide_track_viewer(state), None

    # Calculate visible items (subtract header and footer lines)
    visible_items = max(
        1, viewer_height - TRACK_VIEWER_HEADER_LINES - TRACK_VIEWER_FOOTER_LINES
    )

    # Arrow key / j/k navigation
    if event["type"] == "arrow_up" or (
        event["type"] == "char" and event["char"] == "k"
    ):
        if state.track_viewer_mode == "list":
            # List mode: navigate tracks
            state = move_track_viewer_selection(state, -1, visible_items)
        else:
            # Detail mode: navigate action menu
            playlist_type = state.track_viewer_playlist_type
            action_count = (
                7 if playlist_type == "manual" else 6
            )  # Manual: 7 actions, Smart: 6 actions
            state = move_track_viewer_action_selection(state, -1, action_count)
        return state, None

    if event["type"] == "arrow_down" or (
        event["type"] == "char" and event["char"] == "j"
    ):
        if state.track_viewer_mode == "list":
            # List mode: navigate tracks
            state = move_track_viewer_selection(state, 1, visible_items)
        else:
            # Detail mode: navigate action menu
            playlist_type = state.track_viewer_playlist_type
            action_count = (
                7 if playlist_type == "manual" else 6
            )  # Manual: 7 actions, Smart: 6 actions
            state = move_track_viewer_action_selection(state, 1, action_count)
        return state, None

    # Enter - mode switching or action execution
    if event["type"] == "enter":
        if state.track_viewer_mode == "list":
            # List -> Detail: show track details
            if state.track_viewer_selected < len(state.track_viewer_filtered_tracks):
                state = set_track_viewer_mode(state, "detail")
            return state, None
        else:
            # Detail -> Execute: execute selected action
            return _execute_track_viewer_action(state)

    # Quick keyboard shortcuts (work in both modes, but differ based on context)
    if event["type"] == "char":
        char = event["char"].lower()

        # Get selected track
        if state.track_viewer_selected < len(state.track_viewer_filtered_tracks):
            selected_track = state.track_viewer_filtered_tracks[
                state.track_viewer_selected
            ]
            track_id = selected_track.get("id")

            if char == "p":
                # Play track
                return state, InternalCommand(
                    action="track_viewer_play", data={"track_id": track_id}
                )
            elif char == "e":
                # Edit metadata
                return state, InternalCommand(
                    action="track_viewer_edit", data={"track_id": track_id}
                )
            elif char == "a":
                # Add to another playlist
                return state, InternalCommand(
                    action="track_viewer_add_to_playlist", data={"track_id": track_id}
                )
            elif char == "l":
                # Like track
                return state, InternalCommand(
                    action="track_viewer_like", data={"track_id": track_id}
                )
            elif char == "u":
                # Unlike track
                return state, InternalCommand(
                    action="track_viewer_unlike", data={"track_id": track_id}
                )
            elif char == "d" and state.track_viewer_playlist_type == "manual":
                # Remove from manual playlist (only in list mode)
                if state.track_viewer_mode == "list":
                    playlist_name = state.track_viewer_playlist_name
                    state = show_confirmation(
                        state,
                        "remove_track_from_playlist",
                        {
                            "track_id": track_id,
                            "playlist_name": playlist_name,
                            "track_title": selected_track.get("title", "Unknown"),
                            "track_artist": selected_track.get("artist", "Unknown"),
                        },
                    )
                    return state, None
            elif char == "f" and state.track_viewer_playlist_type == "smart":
                # Edit filters (smart playlists only)
                playlist_id = state.track_viewer_playlist_id
                return state, InternalCommand(
                    action="track_viewer_edit_filters",
                    data={"playlist_id": playlist_id},
                )

    # Handle filter input in list mode
    if state.track_viewer_mode == "list":
        # Backspace - remove last character from filter
        if event["type"] == "backspace":
            if state.track_viewer_filter_query:
                from ..state_selectors import filter_search_tracks

                new_query = state.track_viewer_filter_query[:-1]
                # Use memoized selector (convert list to tuple for cache comparison)
                filtered = filter_search_tracks(new_query, tuple(state.track_viewer_tracks))
                state = update_track_viewer_filter(state, new_query, filtered)
                return state, None

        # Regular character - add to filter (only printable characters, not special shortcuts)
        if event["type"] == "char" and event["char"]:
            char = event["char"]
            # Skip shortcut keys
            if char.lower() not in ["p", "d", "e", "a", "f", "q", "j", "k", "l", "u"]:
                from ..state_selectors import filter_search_tracks

                new_query = state.track_viewer_filter_query + char
                # Use memoized selector (convert list to tuple for cache comparison)
                filtered = filter_search_tracks(new_query, tuple(state.track_viewer_tracks))
                state = update_track_viewer_filter(state, new_query, filtered)
                return state, None

    # For any other key in track viewer mode, consume it and do nothing
    return state, None


def _execute_track_viewer_action(
    state: UIState,
) -> tuple[UIState, InternalCommand | None]:
    """
    Execute the selected action in track viewer detail mode.

    Args:
        state: Current UI state

    Returns:
        Tuple of (updated state, command to execute or None)
    """
    if state.track_viewer_selected >= len(state.track_viewer_filtered_tracks):
        return state, None

    selected_track = state.track_viewer_filtered_tracks[state.track_viewer_selected]
    track_id = selected_track.get("id")
    action_index = state.track_viewer_action_selected
    playlist_type = state.track_viewer_playlist_type

    # Action mapping based on playlist type
    if playlist_type == "manual":
        # Manual playlist actions: Play, Like, Unlike, Remove, Edit, Add, Cancel
        action_map = [
            ("track_viewer_play", {"track_id": track_id}),
            ("track_viewer_like", {"track_id": track_id}),
            ("track_viewer_unlike", {"track_id": track_id}),
            ("track_viewer_remove", {"track_id": track_id}),
            ("track_viewer_edit", {"track_id": track_id}),
            ("track_viewer_add_to_playlist", {"track_id": track_id}),
            (None, {}),  # Cancel
        ]
    else:  # smart playlist
        # Smart playlist actions: Play, Like, Unlike, Edit Metadata, Add, Cancel (Edit Filters is a quick shortcut, not in menu)
        action_map = [
            ("track_viewer_play", {"track_id": track_id}),
            ("track_viewer_like", {"track_id": track_id}),
            ("track_viewer_unlike", {"track_id": track_id}),
            ("track_viewer_edit", {"track_id": track_id}),
            ("track_viewer_add_to_playlist", {"track_id": track_id}),
            (None, {}),  # Cancel
        ]

    action_name, action_data = action_map[action_index]

    if action_name:
        # Execute action
        return state, InternalCommand(action=action_name, data=action_data)
    else:
        # Cancel: go back to list mode
        state = set_track_viewer_mode(state, "list")
        return state, None


def handle_rating_history_key(
    state: UIState, event: dict, viewer_height: int = 10
) -> tuple[UIState | None, str | InternalCommand | None]:
    """
    Handle keyboard events for rating history viewer mode.

    Supports:
    - Arrow Up/Down: Navigate ratings
    - Delete/X: Delete selected rating
    - Esc/Q: Close viewer

    Args:
        state: Current UI state (rating history viewer must be visible)
        event: Parsed key event from parse_key()
        viewer_height: Available height for viewer (for scroll calculations)

    Returns:
        Tuple of (updated state or None if not handled, command to execute or None)
    """
    # Escape or Q - close viewer
    if event["type"] == "escape" or (event["char"] and event["char"].lower() == "q"):
        state = hide_rating_history(state)
        return state, None

    # Arrow Up - move selection up
    if event["type"] == "arrow_up":
        # Calculate visible items based on viewer height (header + footer = 4 lines)
        visible_items = max(1, viewer_height - 4)
        state = move_rating_history_selection(state, -1, visible_items)
        return state, None

    # Arrow Down - move selection down
    if event["type"] == "arrow_down":
        visible_items = max(1, viewer_height - 4)
        state = move_rating_history_selection(state, 1, visible_items)
        return state, None

    # Delete or X - delete selected rating
    if event["type"] == "delete" or (event["char"] and event["char"].lower() == "x"):
        if state.rating_history_ratings and state.rating_history_selected < len(
            state.rating_history_ratings
        ):
            selected_rating = state.rating_history_ratings[state.rating_history_selected]
            rating_id = selected_rating.get("rating_id")

            if rating_id:
                # Delete from database and update state
                from music_minion.core import database

                if database.delete_rating_by_id(rating_id):
                    # Remove from UI list
                    state = delete_rating_history_item(state, state.rating_history_selected)

                    # Return command to log success
                    return state, InternalCommand(
                        action="log_message",
                        data={
                            "message": "✓ Rating deleted",
                            "level": "info",
                        },
                    )
        return state, None

    # For any other key, consume it (don't fall through)
    return state, None


def handle_comparison_history_key(
    state: UIState, event: dict, viewer_height: int = 10
) -> tuple[UIState | None, str | InternalCommand | None]:
    """
    Handle keyboard events for comparison history viewer mode.

    Supports:
    - Arrow Up/Down: Navigate comparisons
    - Esc/Q: Close viewer

    Args:
        state: Current UI state (comparison history viewer must be visible)
        event: Parsed key event from parse_key()
        viewer_height: Available height for viewer (for scroll calculations)

    Returns:
        Tuple of (updated state or None if not handled, command to execute or None)
    """
    # Escape or Q - close viewer
    if event["type"] == "escape" or (event["char"] and event["char"].lower() == "q"):
        state = hide_comparison_history(state)
        return state, None

    # Arrow Up - move selection up
    if event["type"] == "arrow_up":
        # Calculate visible items based on viewer height (header + footer = 4 lines)
        visible_items = max(1, viewer_height - 4)
        state = move_comparison_history_selection(state, -1, visible_items)
        return state, None

    # Arrow Down - move selection down
    if event["type"] == "arrow_down":
        visible_items = max(1, viewer_height - 4)
        state = move_comparison_history_selection(state, 1, visible_items)
        return state, None

    # For any other key, consume it (don't fall through)
    return state, None


def handle_analytics_viewer_key(
    state: UIState, event: dict, viewer_height: int = 10
) -> tuple[UIState | None, str | InternalCommand | None]:
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
    if event["type"] == "escape" or (event["char"] and event["char"].lower() == "q"):
        return hide_analytics_viewer(state), None

    # Use pre-calculated line count (no need to re-format on every keystroke!)
    total_lines = state.analytics_viewer_total_lines
    max_scroll = max(0, total_lines - viewer_height + 1)  # +1 for footer

    # j or down arrow - scroll down
    if (event["char"] and event["char"].lower() == "j") or event[
        "type"
    ] == "arrow_down":
        state = scroll_analytics_viewer(state, delta=1, max_scroll=max_scroll)
        return state, None

    # k or up arrow - scroll up
    if (event["char"] and event["char"].lower() == "k") or event["type"] == "arrow_up":
        state = scroll_analytics_viewer(state, delta=-1, max_scroll=max_scroll)
        return state, None

    # Home - jump to top
    if event["type"] == "home":
        state = scroll_analytics_viewer(state, delta=-999999, max_scroll=max_scroll)
        return state, None

    # End - jump to bottom
    if event["type"] == "end":
        state = scroll_analytics_viewer(state, delta=999999, max_scroll=max_scroll)
        return state, None

    # For any other key in analytics viewer mode, consume it and do nothing
    return state, None


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
    from music_minion.ui.blessed.events.commands.metadata_handlers import (
        handle_metadata_editor_navigation,
        handle_metadata_editor_enter,
        handle_metadata_editor_delete,
        handle_metadata_editor_add,
        handle_metadata_editor_back,
    )
    from music_minion.ui.blessed.state import (
        InternalCommand,
        save_field_edit,
        cancel_field_edit,
        save_add_item,
        cancel_add_item,
        replace,
    )

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


def handle_key(
    state: UIState,
    key: Keystroke,
    palette_height: int = 10,
    analytics_viewer_height: int = 30,
) -> tuple[UIState, str | InternalCommand | None]:
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
        if event["type"] == "enter" or (event["char"] and event["char"].lower() == "y"):
            # Confirmed (Enter defaults to Yes) - trigger action based on confirmation type
            if state.confirmation_type == "delete_playlist":
                command_to_execute = InternalCommand(
                    action="delete_playlist",
                    data={"playlist_name": state.confirmation_data["playlist_name"]},
                )
                state = hide_confirmation(state)
                return state, command_to_execute
            elif state.confirmation_type == "remove_track_from_playlist":
                command_to_execute = InternalCommand(
                    action="remove_track_from_playlist",
                    data={
                        "track_id": state.confirmation_data["track_id"],
                        "playlist_name": state.confirmation_data["playlist_name"],
                    },
                )
                state = hide_confirmation(state)
                return state, command_to_execute
        elif (
            event["char"] and event["char"].lower() == "n" or event["type"] == "escape"
        ):
            # Cancelled
            state = hide_confirmation(state)
            return state, None
        # Ignore other keys during confirmation
        return state, None

    # Handle comparison mode keys (second priority after confirmation)
    if state.comparison.active:
        state_updated, cmd = handle_comparison_key(key, state)
        if state_updated is not None:
            return state_updated, cmd
        # Otherwise fall through to normal key handling (e.g., for seek controls)

    # Handle wizard keys (third priority after confirmation and comparison)
    if state.wizard_active:
        state_updated, cmd = handle_wizard_key(state, event)
        if state_updated is not None:
            return state_updated, cmd

    # Handle track viewer keys (third priority)
    if state.track_viewer_visible:
        state_updated, cmd = handle_track_viewer_key(state, event, palette_height)
        if state_updated is not None:
            return state_updated, cmd

    # Handle rating history viewer keys (fourth priority)
    if state.rating_history_visible:
        state_updated, cmd = handle_rating_history_key(state, event, palette_height)
        if state_updated is not None:
            return state_updated, cmd

    # Handle comparison history viewer keys (fifth priority)
    if state.comparison_history_visible:
        state_updated, cmd = handle_comparison_history_key(state, event, palette_height)
        if state_updated is not None:
            return state_updated, cmd

    # Handle analytics viewer keys (sixth priority)
    if state.analytics_viewer_visible:
        state_updated, cmd = handle_analytics_viewer_key(
            state, event, analytics_viewer_height
        )
        if state_updated is not None:
            return state_updated, cmd

    # Handle metadata editor keys (fifth priority)
    if state.editor_visible:
        state_updated, cmd = handle_metadata_editor_key(state, event)
        if state_updated is not None:
            return state_updated, cmd

    # Handle review mode keys (sixth priority)
    if state.review_mode:
        # In review mode, Enter sends input to review handler
        if event["type"] == "enter" and state.input_text.strip():
            # Return special command to trigger review handler
            user_input = state.input_text.strip()
            state = set_input_text(state, "")
            # Use InternalCommand to pass review input
            return state, InternalCommand(
                action="review_input", data={"input": user_input}
            )

    # Handle Ctrl+C (quit)
    if event["type"] == "ctrl_c":
        return state, "QUIT"

    # Handle Ctrl+L (clear history)
    if event["type"] == "ctrl_l":
        state = clear_history(state)
        return state, None

    # Handle history scrolling (Ctrl+U/D, Home/End) - only when input is empty and no modal active
    # This allows scrolling through command history output (like analytics) without conflicting with typing
    if (
        not state.palette_visible
        and not state.wizard_active
        and not state.track_viewer_visible
        and not state.review_mode
        and not state.input_text
    ):  # Only scroll when input is empty
        if event["type"] == "page_up":
            # Scroll history up by ~visible height (Ctrl+U)
            state = scroll_history_up(state, lines=20)
            return state, None
        elif event["type"] == "page_down":
            # Scroll history down by ~visible height (Ctrl+D)
            state = scroll_history_down(state, lines=20)
            return state, None
        elif event["type"] == "home":
            # Jump to top of history (oldest messages)
            state = scroll_history_to_top(state)
            return state, None
        elif event["type"] == "end":
            # Jump to bottom of history (newest messages)
            state = scroll_history_to_bottom(state)
            return state, None

    # Handle Escape (hide palette or navigate back in search modes)
    if event["type"] == "escape":
        if state.palette_visible:
            # Search mode: Navigate back or close
            if state.palette_mode == "search":
                if state.search_mode == "detail":
                    # Detail -> Search
                    state = set_search_mode(state, "search")
                else:
                    # Search -> Close
                    state = hide_palette(state)
            else:
                # Other modes: just close palette
                state = hide_palette(state)
        return state, None

    # Calculate visible items (subtract header and footer lines)
    visible_items = max(1, palette_height - 2)

    # Handle arrows - palette navigation OR command history navigation
    if event["type"] == "arrow_up":
        if state.palette_visible:
            if state.palette_mode == "search":
                # Search mode: different behavior based on current mode
                if state.search_mode == "search":
                    # Navigate tracks
                    state = move_search_selection(state, -1, visible_items)
                elif state.search_mode == "detail":
                    # Navigate action menu (4 items)
                    state = move_detail_selection(state, -1)
            else:
                # Palette navigation with autofill
                state = move_palette_selection(state, -1, visible_items)
                # Autofill input with selected command (not for search)
                if state.palette_items and state.palette_selected < len(
                    state.palette_items
                ):
                    selected_cmd = state.palette_items[state.palette_selected][
                        1
                    ]  # Command name
                    state = set_input_text(state, selected_cmd)
        else:
            # Command history navigation (when palette not visible)
            state = navigate_history_up(state)
        return state, None

    if event["type"] == "arrow_down":
        if state.palette_visible:
            if state.palette_mode == "search":
                # Search mode: different behavior based on current mode
                if state.search_mode == "search":
                    # Navigate tracks
                    state = move_search_selection(state, 1, visible_items)
                elif state.search_mode == "detail":
                    # Navigate action menu (4 items)
                    state = move_detail_selection(state, 1)
            else:
                # Palette navigation with autofill
                state = move_palette_selection(state, 1, visible_items)
                # Autofill input with selected command (not for search)
                if state.palette_items and state.palette_selected < len(
                    state.palette_items
                ):
                    selected_cmd = state.palette_items[state.palette_selected][
                        1
                    ]  # Command name
                    state = set_input_text(state, selected_cmd)
        else:
            # Command history navigation (when palette not visible)
            state = navigate_history_down(state)
        return state, None

    # Handle Enter (execute command or select palette item)
    if event["type"] == "enter":
        command_to_execute = None

        if state.palette_visible:
            # Search mode: Navigate to detail or execute action
            if state.palette_mode == "search":
                if state.search_filtered_tracks and state.search_selected < len(
                    state.search_filtered_tracks
                ):
                    selected_track = state.search_filtered_tracks[state.search_selected]
                    track_id = selected_track.get("id")

                    if track_id is not None:
                        if state.search_mode == "search":
                            # Search -> Detail: Show track details
                            state = set_search_mode(state, "detail")
                            return state, None
                        elif state.search_mode == "detail":
                            # Detail -> Execute: Execute selected action
                            action_map = [
                                ("search_play_track", {}),
                                ("search_add_to_playlist", {}),
                                ("search_edit_metadata", {}),
                                (None, {}),  # Cancel (do nothing)
                            ]
                            action_name, action_data = action_map[
                                state.search_detail_selection
                            ]

                            if action_name:
                                # Close search and execute action
                                state = hide_palette(state)
                                action_data["track_id"] = track_id
                                return state, InternalCommand(
                                    action=action_name, data=action_data
                                )
                            else:
                                # Cancel: go back to search
                                state = set_search_mode(state, "search")
                                return state, None
                return state, None

            # Command/Playlist mode: select item
            elif state.palette_items:
                if state.palette_selected < len(state.palette_items):
                    selected = state.palette_items[state.palette_selected]

                    # Different handling based on palette mode
                    if state.palette_mode == "playlist":
                        # For playlist mode, send special command with playlist name
                        playlist_name = selected[1]  # Playlist name
                        command_to_execute = f"__SELECT_PLAYLIST__ {playlist_name}"
                    elif state.palette_mode == "device":
                        # For device mode, send special command with device command
                        device_command = selected[2]  # Command to execute
                        command_to_execute = device_command
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
    if event["type"] == "backspace":
        state = delete_input_char(state)
        state = reset_history_navigation(state)

        # Update palette filter if visible
        if state.palette_visible:
            if state.palette_mode == "search":
                # Filter tracks in search mode
                from ..state_selectors import filter_search_tracks

                # Use memoized selector (convert list to tuple for cache comparison)
                filtered = filter_search_tracks(state.input_text, tuple(state.search_all_tracks))
                state = update_search_query(state, state.input_text, filtered)
            elif state.palette_mode == "playlist":
                # Filter playlists by name
                from ..components.palette import (
                    filter_playlist_items,
                    load_playlist_items,
                )

                all_items = load_playlist_items(state.active_library)
                filtered = filter_playlist_items(state.input_text, all_items)
                state = update_palette_filter(state, state.input_text, filtered)
            else:
                # Filter commands
                query = (
                    state.input_text[1:]
                    if state.input_text.startswith("/")
                    else state.input_text
                )
                filtered = filter_commands(query, COMMAND_DEFINITIONS)
                state = update_palette_filter(state, query, filtered)

        return state, None

    # Handle 'v' key - view playlist tracks (only in playlist palette mode)
    if event["type"] == "char" and event["char"] == "v":
        if state.palette_visible and state.palette_mode == "playlist":
            # Get selected playlist
            if state.palette_items and state.palette_selected < len(
                state.palette_items
            ):
                selected = state.palette_items[state.palette_selected]
                playlist_name = selected[1]  # Playlist name

                # Close palette and open track viewer
                state = hide_palette(state)
                return state, InternalCommand(
                    action="view_playlist_tracks", data={"playlist_name": playlist_name}
                )
            return state, None

    # Handle delete key
    if event["type"] == "delete":
        # Check if in playlist palette mode - delete selected playlist
        if state.palette_visible and state.palette_mode == "playlist":
            # Get selected playlist
            if state.palette_items and state.palette_selected < len(
                state.palette_items
            ):
                selected = state.palette_items[state.palette_selected]
                playlist_name = selected[1]  # Playlist name

                # Show confirmation dialog
                state = show_confirmation(
                    state, "delete_playlist", {"playlist_name": playlist_name}
                )
            return state, None
        else:
            # Normal delete behavior (backspace)
            state = delete_input_char(state)
            state = reset_history_navigation(state)

            # Update palette filter if visible
            if state.palette_visible:
                # Remove "/" prefix for filtering
                query = (
                    state.input_text[1:]
                    if state.input_text.startswith("/")
                    else state.input_text
                )
                filtered = filter_commands(query, COMMAND_DEFINITIONS)
                # Convert to format expected by state (category, cmd, icon, desc)
                state = update_palette_filter(state, query, filtered)

            return state, None

    # Handle seek controls in normal mode (no modals, no input)
    if (
        not state.palette_visible
        and not state.track_viewer_visible
        and not state.wizard_active
        and not state.analytics_viewer_visible
        and not state.editor_visible
        and not state.review_mode
        and not state.input_text
    ):
        # Numeric keys 0-9: Jump to percentage (0%-90%)
        if event["type"] == "char" and event["char"] and event["char"].isdigit():
            digit = int(event["char"])
            percentage = digit * 10
            return state, InternalCommand(
                action="seek_percentage", data={"percentage": percentage}
            )

        # Left/Right arrows: Seek ±5 seconds
        if event["type"] == "arrow_left":
            return state, InternalCommand(
                action="seek_relative", data={"seconds": -5.0}
            )
        if event["type"] == "arrow_right":
            return state, InternalCommand(
                action="seek_relative", data={"seconds": 5.0}
            )

        # Shift+Left/Right: Seek ±1 second
        if event["type"] == "shift_arrow_left":
            return state, InternalCommand(
                action="seek_relative", data={"seconds": -1.0}
            )
        if event["type"] == "shift_arrow_right":
            return state, InternalCommand(
                action="seek_relative", data={"seconds": 1.0}
            )

    # Handle regular characters
    if event["type"] == "char" and event["char"]:
        char = event["char"]

        # Shortcut keys in search detail mode (p/a/e for quick actions)
        if (
            state.palette_visible
            and state.palette_mode == "search"
            and state.search_mode == "detail"
        ):
            if state.search_filtered_tracks and state.search_selected < len(
                state.search_filtered_tracks
            ):
                track_id = state.search_filtered_tracks[state.search_selected].get("id")

                if track_id is not None:
                    if char.lower() == "p":  # Play
                        state = hide_palette(state)
                        return state, InternalCommand(
                            action="search_play_track", data={"track_id": track_id}
                        )
                    elif char.lower() == "a":  # Add to playlist
                        state = hide_palette(state)
                        return state, InternalCommand(
                            action="search_add_to_playlist", data={"track_id": track_id}
                        )
                    elif char.lower() == "e":  # Edit metadata
                        state = hide_palette(state)
                        return state, InternalCommand(
                            action="search_edit_metadata", data={"track_id": track_id}
                        )

        # Reset history navigation when typing
        state = reset_history_navigation(state)

        # Check if space closes palette after selection
        if char == " " and state.palette_visible and state.input_text:
            state = hide_palette(state)
            state = append_input_char(state, char)
            return state, None

        # Check if "/" triggers palette
        if char == "/" and not state.input_text:
            state = append_input_char(state, char)
            # Show palette with all commands
            filtered = filter_commands("", COMMAND_DEFINITIONS)
            state = update_palette_filter(state, "", filtered)
            state = show_palette(state)
        else:
            state = append_input_char(state, char)

            # Update palette filter if visible
            if state.palette_visible:
                if state.palette_mode == "search":
                    # Filter tracks in search mode
                    from ..state_selectors import filter_search_tracks

                    # Use memoized selector (convert list to tuple for cache comparison)
                    filtered = filter_search_tracks(state.input_text, tuple(state.search_all_tracks))
                    state = update_search_query(state, state.input_text, filtered)
                elif state.palette_mode == "playlist":
                    # Filter playlists by name
                    from ..components.palette import (
                        filter_playlist_items,
                        load_playlist_items,
                    )

                    all_items = load_playlist_items(state.active_library)
                    filtered = filter_playlist_items(state.input_text, all_items)
                    state = update_palette_filter(state, state.input_text, filtered)
                else:
                    # Filter commands
                    query = (
                        state.input_text[1:]
                        if state.input_text.startswith("/")
                        else state.input_text
                    )
                    filtered = filter_commands(query, COMMAND_DEFINITIONS)
                    state = update_palette_filter(state, query, filtered)

        return state, None

    return state, None


def handle_comparison_key(key: Keystroke, state: UIState) -> tuple[UIState, InternalCommand | None]:
    """
    Handle keyboard input during comparison mode.

    Keyboard shortcuts:
    - Left Arrow / A: Highlight Track A (left side)
    - Right Arrow / D: Highlight Track B (right side)
    - Space: Play currently highlighted track
    - Enter: Choose highlighted track as winner, record comparison
    - Esc / Q: Exit comparison mode, restore playback

    Args:
        key: blessed Keystroke
        state: Current UI state with comparison mode active

    Returns:
        Tuple of (updated state, command to execute or None)
    """
    from loguru import logger

    comparison = state.comparison

    # Parse key event to get consistent event dictionary
    event = parse_key(key)

    # Log key press for debugging
    logger.debug(f"Comparison mode key: name={key.name}, event_type={event['type']}, char={event.get('char')}")

    # Arrow keys or A/D: Change highlighted track
    if event["type"] == "arrow_left" or (event["type"] == "char" and event["char"] and event["char"].lower() == "a"):
        new_comparison = dataclasses.replace(comparison, highlighted="a")
        new_state = dataclasses.replace(state, comparison=new_comparison)
        return new_state, None

    elif event["type"] == "arrow_right" or (event["type"] == "char" and event["char"] and event["char"].lower() == "d"):
        new_comparison = dataclasses.replace(comparison, highlighted="b")
        new_state = dataclasses.replace(state, comparison=new_comparison)
        return new_state, None

    # Space: Play highlighted track
    elif key == ' ' or event["type"] == "char" and event["char"] == " ":
        track = comparison.track_a if comparison.highlighted == "a" else comparison.track_b
        # Use InternalCommand to trigger playback
        return state, InternalCommand(
            action="comparison_play_track",
            data={"track": track}
        )

    # Enter: Choose highlighted track as winner
    elif event["type"] == "enter":
        return handle_comparison_choice(state, comparison.highlighted)

    # Esc or Q: Exit comparison mode
    elif event["type"] == "escape" or (event["type"] == "char" and event["char"] and event["char"].lower() == "q"):
        return exit_comparison_mode(state)

    # Key not handled by comparison mode - allow fallthrough to normal handling
    return None, None


def handle_comparison_choice(state: UIState, winner_side: str) -> tuple[UIState, InternalCommand | None]:
    """
    Record comparison, update ratings, load next pair or end session.

    Args:
        state: Current UI state
        winner_side: "a" or "b"

    Returns:
        Tuple of (updated state, command to execute or None)
    """
    comparison = state.comparison

    # Determine winner and loser
    if winner_side == "a":
        winner = comparison.track_a
        loser = comparison.track_b
    else:
        winner = comparison.track_b
        loser = comparison.track_a

    # Get current ratings
    winner_rating_obj = get_or_create_rating(winner['id'])
    loser_rating_obj = get_or_create_rating(loser['id'])

    # Calculate K-factors
    winner_k = get_k_factor(winner_rating_obj.comparison_count)
    loser_k = get_k_factor(loser_rating_obj.comparison_count)

    # Use average K-factor for update
    k = (winner_k + loser_k) / 2

    # Update ratings using Elo
    new_winner_rating, new_loser_rating = update_ratings(
        winner_rating_obj.rating,
        loser_rating_obj.rating,
        k
    )

    # Record comparison in database
    record_comparison(
        track_a_id=comparison.track_a['id'],
        track_b_id=comparison.track_b['id'],
        winner_id=winner['id'],
        track_a_rating_before=winner_rating_obj.rating if winner_side == "a" else loser_rating_obj.rating,
        track_b_rating_before=loser_rating_obj.rating if winner_side == "a" else winner_rating_obj.rating,
        track_a_rating_after=new_winner_rating if winner_side == "a" else new_loser_rating,
        track_b_rating_after=new_loser_rating if winner_side == "a" else new_winner_rating,
        session_id=comparison.session_id
    )

    # Increment comparison count
    new_comparisons_done = comparison.comparisons_done + 1

    # Check if session complete
    if new_comparisons_done >= comparison.target_comparisons:
        return end_comparison_session(state)

    # Load next pair
    # Get filtered tracks from comparison state (stored by command handler)
    filtered_tracks = comparison.filtered_tracks
    ratings_cache = comparison.ratings_cache or {}

    # Update ratings cache
    ratings_cache[winner['id']] = {
        'rating': new_winner_rating,
        'comparison_count': winner_rating_obj.comparison_count + 1
    }
    ratings_cache[loser['id']] = {
        'rating': new_loser_rating,
        'comparison_count': loser_rating_obj.comparison_count + 1
    }

    # Select next pair
    if not filtered_tracks or len(filtered_tracks) < 2:
        # Unexpected: no tracks to compare
        log("No more tracks to compare", level="warning")
        return end_comparison_session(state)

    track_a, track_b = select_strategic_pair(filtered_tracks, ratings_cache)

    # Update comparison state
    new_comparison = dataclasses.replace(
        comparison,
        track_a=track_a,
        track_b=track_b,
        highlighted="a",  # Reset to track A
        comparisons_done=new_comparisons_done,
        ratings_cache=ratings_cache
    )

    new_state = dataclasses.replace(state, comparison=new_comparison)

    return new_state, None


def end_comparison_session(state: UIState) -> tuple[UIState, InternalCommand | None]:
    """
    End comparison session, show summary, restore playback.

    Args:
        state: Current UI state

    Returns:
        Tuple of (updated state, command to execute or None)
    """
    comparison = state.comparison

    # Get coverage stats
    rated_count, total_count = get_ratings_coverage()

    # Show session complete message
    log(f"Session complete! {comparison.comparisons_done} comparisons made.", level="info")
    log(f"Coverage: {rated_count}/{total_count} tracks rated (20+ comparisons)", level="info")

    # Clear comparison state
    new_comparison = dataclasses.replace(
        comparison,
        active=False,
        track_a=None,
        track_b=None,
        saved_player_state=None,
        filtered_tracks=[],
        ratings_cache=None
    )

    new_state = dataclasses.replace(state, comparison=new_comparison)

    # Use InternalCommand to restore playback if needed
    if comparison.saved_player_state:
        return new_state, InternalCommand(
            action="comparison_restore_playback",
            data={"player_state": comparison.saved_player_state}
        )

    return new_state, None


def exit_comparison_mode(state: UIState) -> tuple[UIState, InternalCommand | None]:
    """
    Exit comparison mode early (user pressed Esc).

    Args:
        state: Current UI state

    Returns:
        Tuple of (updated state, command to execute or None)
    """
    comparison = state.comparison

    # Show exit message
    log(f"Session ended. {comparison.comparisons_done}/{comparison.target_comparisons} comparisons completed.", level="info")

    # Clear comparison state
    new_comparison = dataclasses.replace(
        comparison,
        active=False,
        track_a=None,
        track_b=None,
        saved_player_state=None,
        filtered_tracks=[],
        ratings_cache=None
    )

    new_state = dataclasses.replace(state, comparison=new_comparison)

    return new_state, None
