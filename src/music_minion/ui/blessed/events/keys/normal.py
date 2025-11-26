"""Normal mode keyboard handlers (palette, search, history, seek controls)."""

from music_minion.ui.blessed.state import (
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
    update_search_query,
    move_search_selection,
    set_search_mode,
    move_detail_selection,
)
from music_minion.ui.blessed.styles.palette import filter_commands, COMMAND_DEFINITIONS
from music_minion.ui.blessed.state_selectors import filter_search_tracks
from music_minion.ui.blessed.components.palette import (
    filter_playlist_items,
    load_playlist_items,
)


def _update_palette_filter(state: UIState) -> UIState:
    """Update palette filter based on current mode and input text."""
    if not state.palette_visible:
        return state

    if state.palette_mode == "search":
        # Filter tracks in search mode (use memoized selector)
        filtered = filter_search_tracks(state.input_text, tuple(state.search_all_tracks))
        return update_search_query(state, state.input_text, filtered)
    elif state.palette_mode == "playlist":
        # Filter playlists by name
        all_items = load_playlist_items(state.active_library)
        filtered = filter_playlist_items(state.input_text, all_items)
        return update_palette_filter(state, state.input_text, filtered)
    else:
        # Filter commands (remove "/" prefix)
        query = state.input_text[1:] if state.input_text.startswith("/") else state.input_text
        filtered = filter_commands(query, COMMAND_DEFINITIONS)
        return update_palette_filter(state, query, filtered)


def _confirm_action(state: UIState) -> tuple[UIState, InternalCommand]:
    """Execute confirmed action based on confirmation type."""
    if state.confirmation_type == "delete_playlist":
        cmd = InternalCommand(
            action="delete_playlist",
            data={"playlist_name": state.confirmation_data["playlist_name"]},
        )
    else:  # remove_track_from_playlist
        cmd = InternalCommand(
            action="remove_track_from_playlist",
            data={
                "track_id": state.confirmation_data["track_id"],
                "playlist_name": state.confirmation_data["playlist_name"],
            },
        )
    return hide_confirmation(state), cmd


def _handle_confirmation_dialog(
    state: UIState, event: dict
) -> tuple[UIState, str | InternalCommand | None] | None:
    """Handle confirmation dialog keys. Returns None if not in confirmation mode."""
    if not state.confirmation_active:
        return None

    # Enter or 'y' confirms
    if event["type"] == "enter" or (event["char"] and event["char"].lower() == "y"):
        return _confirm_action(state)

    # 'n' or Escape cancels
    if (event["char"] and event["char"].lower() == "n") or event["type"] == "escape":
        return hide_confirmation(state), None

    # Ignore other keys during confirmation
    return state, None


def _handle_review_mode(
    state: UIState, event: dict
) -> tuple[UIState, str | InternalCommand | None] | None:
    """Handle review mode input. Returns None if not in review mode."""
    if not state.review_mode:
        return None

    # Enter sends input to review handler
    if event["type"] == "enter" and state.input_text.strip():
        user_input = state.input_text.strip()
        state = set_input_text(state, "")
        return state, InternalCommand(action="review_input", data={"input": user_input})

    return None


def _is_idle_mode(state: UIState) -> bool:
    """Check if UI is in idle mode (no modals, no input)."""
    return (
        not state.palette_visible
        and not state.track_viewer_visible
        and not state.wizard_active
        and not state.analytics_viewer_visible
        and not state.editor_visible
        and not state.review_mode
        and not state.input_text
    )


def _handle_history_scrolling(
    state: UIState, event: dict
) -> tuple[UIState, None] | None:
    """Handle history scrolling keys (Page Up/Down, Home/End)."""
    # Only allow scrolling when input is empty and no modal active
    if not _is_idle_mode(state) or state.input_text:
        return None

    if event["type"] == "page_up":
        return scroll_history_up(state, lines=20), None
    elif event["type"] == "page_down":
        return scroll_history_down(state, lines=20), None
    elif event["type"] == "home":
        return scroll_history_to_top(state), None
    elif event["type"] == "end":
        return scroll_history_to_bottom(state), None

    return None


def _handle_escape(state: UIState, event: dict) -> tuple[UIState, None] | None:
    """Handle Escape key (hide palette or navigate back)."""
    if event["type"] != "escape":
        return None

    if state.palette_visible:
        # Search mode: Navigate back or close
        if state.palette_mode == "search" and state.search_mode == "detail":
            return set_search_mode(state, "search"), None
        else:
            return hide_palette(state), None

    return state, None


def _autofill_command(state: UIState) -> UIState:
    """Autofill input with selected command from palette."""
    if state.palette_items and state.palette_selected < len(state.palette_items):
        selected_cmd = state.palette_items[state.palette_selected][1]
        return set_input_text(state, selected_cmd)
    return state


def _handle_arrow_up(
    state: UIState, visible_items: int
) -> tuple[UIState, None]:
    """Handle arrow up navigation."""
    if state.palette_visible:
        if state.palette_mode == "search":
            if state.search_mode == "search":
                return move_search_selection(state, -1, visible_items), None
            elif state.search_mode == "detail":
                return move_detail_selection(state, -1), None
        else:
            # Palette navigation with autofill
            state = move_palette_selection(state, -1, visible_items)
            return _autofill_command(state), None
    else:
        # Command history navigation
        return navigate_history_up(state), None


def _handle_arrow_down(
    state: UIState, visible_items: int
) -> tuple[UIState, None]:
    """Handle arrow down navigation."""
    if state.palette_visible:
        if state.palette_mode == "search":
            if state.search_mode == "search":
                return move_search_selection(state, 1, visible_items), None
            elif state.search_mode == "detail":
                return move_detail_selection(state, 1), None
        else:
            # Palette navigation with autofill
            state = move_palette_selection(state, 1, visible_items)
            return _autofill_command(state), None
    else:
        # Command history navigation
        return navigate_history_down(state), None


def _execute_search_action(
    state: UIState, track_id: int
) -> tuple[UIState, InternalCommand | None]:
    """Execute selected search detail action."""
    action_map = [
        ("search_play_track", {}),
        ("search_add_to_playlist", {}),
        ("search_edit_metadata", {}),
        (None, {}),  # Cancel
    ]
    action_name, action_data = action_map[state.search_detail_selection]

    if action_name:
        state = hide_palette(state)
        action_data["track_id"] = track_id
        return state, InternalCommand(action=action_name, data=action_data)
    else:
        return set_search_mode(state, "search"), None


def _handle_enter_search_mode(
    state: UIState,
) -> tuple[UIState, str | InternalCommand | None] | None:
    """Handle Enter in search mode."""
    if state.palette_mode != "search":
        return None

    if not state.search_filtered_tracks or state.search_selected >= len(
        state.search_filtered_tracks
    ):
        return state, None

    track_id = state.search_filtered_tracks[state.search_selected].get("id")
    if track_id is None:
        return state, None

    if state.search_mode == "search":
        return set_search_mode(state, "detail"), None
    elif state.search_mode == "detail":
        return _execute_search_action(state, track_id)

    return state, None


def _handle_enter_palette_selection(
    state: UIState,
) -> tuple[UIState, str | InternalCommand | None]:
    """Handle Enter to select palette item."""
    if not state.palette_items or state.palette_selected >= len(state.palette_items):
        return state, None

    selected = state.palette_items[state.palette_selected]

    if state.palette_mode == "playlist":
        # Enter views playlist tracks
        playlist_name = selected[1]
        state = hide_palette(state)
        state = set_input_text(state, "")
        return state, InternalCommand(
            action="view_playlist_tracks", data={"playlist_name": playlist_name}
        )
    elif state.palette_mode == "device":
        command = selected[2]
        state = hide_palette(state)
        state = set_input_text(state, "")
        return state, command
    elif state.palette_mode == "rankings":
        # Rankings items: (rank, artist_title, icon, rating_info, track_id)
        track_id = selected[4]
        state = hide_palette(state)
        return state, InternalCommand(action="track_viewer_play", data={"track_id": track_id})
    else:
        command = selected[1]
        state = hide_palette(state)
        state = set_input_text(state, "")
        return state, command


def _handle_enter(
    state: UIState, event: dict
) -> tuple[UIState, str | InternalCommand | None] | None:
    """Handle Enter key (execute command or select palette item)."""
    if event["type"] != "enter":
        return None

    if state.palette_visible:
        # Try search mode first
        result = _handle_enter_search_mode(state)
        if result:
            return result
        # Fall back to palette selection
        return _handle_enter_palette_selection(state)
    else:
        # Execute typed command
        if state.input_text.strip():
            command = state.input_text.strip()
            state = set_input_text(state, "")
            return state, command

    return state, None


def _handle_backspace(
    state: UIState, event: dict
) -> tuple[UIState, None] | None:
    """Handle backspace key (delete character and update filter)."""
    if event["type"] != "backspace":
        return None

    state = delete_input_char(state)
    state = reset_history_navigation(state)
    state = _update_palette_filter(state)
    return state, None


def _handle_spacebar_playlist_activate(
    state: UIState, event: dict
) -> tuple[UIState, str | None] | None:
    """Handle spacebar to activate playlist and start playing."""
    if event["type"] != "char" or event["char"] != " ":
        return None

    if not (state.palette_visible and state.palette_mode == "playlist"):
        return None

    if state.palette_items and state.palette_selected < len(state.palette_items):
        playlist_name = state.palette_items[state.palette_selected][1]
        command = f"__SELECT_PLAYLIST__ {playlist_name}"
        state = hide_palette(state)
        state = set_input_text(state, "")
        return state, command

    return state, None


def _handle_play_ranking(
    state: UIState, event: dict
) -> tuple[UIState, InternalCommand | None] | None:
    """Handle 'p' key to play selected track in rankings mode."""
    if event["type"] != "char" or event["char"] != "p":
        return None

    if not (state.palette_visible and state.palette_mode == "rankings"):
        return None

    if state.palette_items and state.palette_selected < len(state.palette_items):
        # Rankings items: (rank, artist_title, icon, rating_info, track_id)
        track_id = state.palette_items[state.palette_selected][4]
        state = hide_palette(state)
        return state, InternalCommand(
            action="track_viewer_play", data={"track_id": track_id}
        )

    return state, None


def _handle_delete_key(
    state: UIState, event: dict
) -> tuple[UIState, None] | None:
    """Handle delete key (delete playlist or backspace)."""
    if event["type"] != "delete":
        return None

    # Delete playlist if in playlist palette mode
    if state.palette_visible and state.palette_mode == "playlist":
        if state.palette_items and state.palette_selected < len(state.palette_items):
            playlist_name = state.palette_items[state.palette_selected][1]
            state = show_confirmation(state, "delete_playlist", {"playlist_name": playlist_name})
        return state, None
    else:
        # Normal delete (backspace)
        state = delete_input_char(state)
        state = reset_history_navigation(state)
        state = _update_palette_filter(state)
        return state, None


def _handle_seek_controls(
    state: UIState, event: dict
) -> tuple[UIState, InternalCommand] | None:
    """Handle seek controls (0-9, arrows, shift+arrows) in idle mode."""
    if not _is_idle_mode(state):
        return None

    # Numeric keys 0-9: Jump to percentage
    if event["type"] == "char" and event["char"] and event["char"].isdigit():
        percentage = int(event["char"]) * 10
        return state, InternalCommand(action="seek_percentage", data={"percentage": percentage})

    # Map event types to seek commands
    seek_map = {
        "arrow_left": -5.0,
        "arrow_right": 5.0,
        "shift_arrow_left": -1.0,
        "shift_arrow_right": 1.0,
    }
    seconds = seek_map.get(event["type"])
    if seconds is not None:
        return state, InternalCommand(action="seek_relative", data={"seconds": seconds})

    return None


def _handle_search_shortcuts(
    state: UIState, char: str
) -> tuple[UIState, InternalCommand] | None:
    """Handle search detail mode shortcuts (p/a/e)."""
    if not (
        state.palette_visible
        and state.palette_mode == "search"
        and state.search_mode == "detail"
    ):
        return None

    if not state.search_filtered_tracks or state.search_selected >= len(
        state.search_filtered_tracks
    ):
        return None

    track_id = state.search_filtered_tracks[state.search_selected].get("id")
    if track_id is None:
        return None

    action_map = {"p": "search_play_track", "a": "search_add_to_playlist", "e": "search_edit_metadata"}
    action = action_map.get(char.lower())

    if action:
        return hide_palette(state), InternalCommand(action=action, data={"track_id": track_id})

    return None


def _trigger_command_palette(state: UIState) -> UIState:
    """Trigger command palette with '/' character."""
    state = append_input_char(state, "/")
    filtered = filter_commands("", COMMAND_DEFINITIONS)
    state = update_palette_filter(state, "", filtered)
    return show_palette(state)


def _handle_character_input(
    state: UIState, event: dict
) -> tuple[UIState, str | InternalCommand | None] | None:
    """Handle regular character input and filtering."""
    if event["type"] != "char" or not event["char"]:
        return None

    char = event["char"]

    # Check for search shortcuts first
    shortcut_result = _handle_search_shortcuts(state, char)
    if shortcut_result:
        return shortcut_result

    # Reset history navigation when typing
    state = reset_history_navigation(state)

    # Space closes palette after selection
    if char == " " and state.palette_visible and state.input_text:
        state = hide_palette(state)
        state = append_input_char(state, char)
        return state, None

    # "/" triggers palette
    if char == "/" and not state.input_text:
        return _trigger_command_palette(state), None

    # Regular character input
    state = append_input_char(state, char)
    state = _update_palette_filter(state)
    return state, None


def handle_normal_mode_key(
    state: UIState,
    event: dict,
    palette_height: int = 10,
) -> tuple[UIState, str | InternalCommand | None]:
    """
    Handle keyboard events for normal mode (no modals active).

    Dispatches to focused sub-handlers for each key type:
    - Confirmation dialogs (highest priority)
    - Review mode input
    - Global shortcuts (Ctrl+C, Ctrl+L)
    - History scrolling (Page Up/Down, Home/End)
    - Escape (hide palette or navigate back)
    - Arrow navigation (palette or command history)
    - Enter (execute command or select palette item)
    - Backspace/Delete (input editing + filter updates)
    - Space (activate playlist)
    - Seek controls (0-9, arrows, shift+arrows)
    - Regular characters (input + filtering)

    Args:
        state: Current UI state
        event: Parsed key event from parse_key()
        palette_height: Available height for palette (for scroll calculations)

    Returns:
        Tuple of (updated state, command to execute or None)
    """
    # Priority order: confirmation > review > shortcuts > navigation > input

    # Confirmation dialog (highest priority)
    result = _handle_confirmation_dialog(state, event)
    if result is not None:
        return result

    # Review mode
    result = _handle_review_mode(state, event)
    if result is not None:
        return result

    # Global shortcuts
    if event["type"] == "ctrl_c":
        return state, "QUIT"
    if event["type"] == "ctrl_l":
        return clear_history(state), None

    # History scrolling
    result = _handle_history_scrolling(state, event)
    if result is not None:
        return result

    # Escape
    result = _handle_escape(state, event)
    if result is not None:
        return result

    # Arrow navigation
    visible_items = max(1, palette_height - 2)
    if event["type"] == "arrow_up":
        return _handle_arrow_up(state, visible_items)
    if event["type"] == "arrow_down":
        return _handle_arrow_down(state, visible_items)

    # Enter
    result = _handle_enter(state, event)
    if result is not None:
        return result

    # Backspace
    result = _handle_backspace(state, event)
    if result is not None:
        return result

    # Spacebar activates playlist
    result = _handle_spacebar_playlist_activate(state, event)
    if result is not None:
        return result

    # Play ranking ('p' key)
    result = _handle_play_ranking(state, event)
    if result is not None:
        return result

    # Delete key
    result = _handle_delete_key(state, event)
    if result is not None:
        return result

    # Seek controls
    result = _handle_seek_controls(state, event)
    if result is not None:
        return result

    # Regular character input
    result = _handle_character_input(state, event)
    if result is not None:
        return result

    return state, None
