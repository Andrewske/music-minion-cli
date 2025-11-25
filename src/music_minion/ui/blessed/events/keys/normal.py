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


def handle_normal_mode_key(
    state: UIState,
    event: dict,
    palette_height: int = 10,
) -> tuple[UIState, str | InternalCommand | None]:
    """
    Handle keyboard events for normal mode (no modals active).

    Handles:
    - Confirmation dialogs
    - Review mode input
    - Ctrl+C (quit)
    - Ctrl+L (clear history)
    - History scrolling (Page Up/Down, Home/End)
    - Escape (hide palette or navigate back in search)
    - Arrow navigation (palette or command history)
    - Enter (execute command or select palette item)
    - Backspace/Delete (input editing + filter updates)
    - 'v' key (view playlist tracks)
    - Delete key (delete playlist)
    - Seek controls (0-9, arrows, shift+arrows)
    - Regular characters (input + filtering)

    Args:
        state: Current UI state
        event: Parsed key event from parse_key()
        palette_height: Available height for palette (for scroll calculations)

    Returns:
        Tuple of (updated state, command to execute or None)
    """
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

    # Handle review mode keys
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
                from music_minion.ui.blessed.state_selectors import filter_search_tracks

                # Use memoized selector (convert list to tuple for cache comparison)
                filtered = filter_search_tracks(state.input_text, tuple(state.search_all_tracks))
                state = update_search_query(state, state.input_text, filtered)
            elif state.palette_mode == "playlist":
                # Filter playlists by name
                from music_minion.ui.blessed.components.palette import (
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
                    from music_minion.ui.blessed.state_selectors import filter_search_tracks

                    # Use memoized selector (convert list to tuple for cache comparison)
                    filtered = filter_search_tracks(state.input_text, tuple(state.search_all_tracks))
                    state = update_search_query(state, state.input_text, filtered)
                elif state.palette_mode == "playlist":
                    # Filter playlists by name
                    from music_minion.ui.blessed.components.palette import (
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
