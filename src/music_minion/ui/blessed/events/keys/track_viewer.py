"""Track viewer mode keyboard handlers."""

from music_minion.ui.blessed.state import (
    UIState,
    InternalCommand,
    hide_track_viewer,
    move_track_viewer_selection,
    set_track_viewer_mode,
    move_track_viewer_action_selection,
    update_track_viewer_filter,
    show_confirmation,
)
from music_minion.ui.blessed.components.track_viewer import (
    TRACK_VIEWER_HEADER_LINES,
    TRACK_VIEWER_FOOTER_LINES,
)


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
            elif char == "b" and state.track_viewer_playlist_type == "manual":
                # Enter playlist builder mode (only for manual playlists)
                return hide_track_viewer(state), InternalCommand(
                    action="enter_playlist_builder",
                    data={
                        "playlist_id": state.track_viewer_playlist_id,
                        "playlist_name": state.track_viewer_playlist_name,
                    },
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
                from music_minion.ui.blessed.state_selectors import filter_search_tracks

                new_query = state.track_viewer_filter_query[:-1]
                # Use memoized selector (convert list to tuple for cache comparison)
                filtered = filter_search_tracks(new_query, tuple(state.track_viewer_tracks))
                state = update_track_viewer_filter(state, new_query, filtered)
                return state, None

        # Regular character - add to filter (only printable characters, not special shortcuts)
        if event["type"] == "char" and event["char"]:
            char = event["char"]
            # Skip shortcut keys
            if char.lower() not in ["p", "d", "e", "a", "f", "q", "j", "k", "l", "u", "b"]:
                from music_minion.ui.blessed.state_selectors import filter_search_tracks

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
