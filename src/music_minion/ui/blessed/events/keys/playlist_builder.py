"""Key handler for playlist builder mode."""

from typing import Optional, Union

from music_minion.ui.blessed.state import (
    UIState,
    InternalCommand,
    move_builder_selection,
    show_builder_sort_dropdown,
    show_builder_filter_dropdown,
    move_builder_dropdown_selection,
    select_builder_sort_field,
    select_builder_filter_field,
    select_builder_filter_operator,
    update_builder_filter_value,
    backspace_builder_filter_value,
    confirm_builder_filter,
    remove_builder_filter,
    clear_builder_filters,
    cancel_builder_dropdown,
    hide_playlist_builder,
    toggle_builder_track,
)


def handle_playlist_builder_key(
    state: UIState,
    event: dict,
    viewer_height: int = 20,
) -> tuple[Optional[UIState], Optional[Union[str, InternalCommand]]]:
    """Handle keyboard events for playlist builder mode.

    Returns:
        (state, command): Updated state and optional command to execute
        (None, None): Event not handled
    """
    builder = state.builder

    # Delegate to dropdown handlers if dropdown is open
    if builder.dropdown_mode == "sort":
        return _handle_sort_dropdown_key(state, event)
    elif builder.dropdown_mode == "filter_field":
        return _handle_filter_field_key(state, event)
    elif builder.dropdown_mode == "filter_operator":
        return _handle_filter_operator_key(state, event)
    elif builder.dropdown_mode == "filter_value":
        return _handle_filter_value_key(state, event)

    # Main builder mode
    return _handle_main_builder_key(state, event, viewer_height)


def _handle_main_builder_key(
    state: UIState,
    event: dict,
    viewer_height: int,
) -> tuple[Optional[UIState], Optional[Union[str, InternalCommand]]]:
    """Handle keys in main builder view (no dropdown open)."""
    event_type = event.get("type")
    char = event.get("char", "")

    # Navigation
    if event_type == "arrow_down" or char == "j":
        return move_builder_selection(state, 1, viewer_height), None

    if event_type == "arrow_up" or char == "k":
        return move_builder_selection(state, -1, viewer_height), None

    # Toggle track in playlist
    if char == " ":
        track = _get_selected_track(state)
        if track:
            return toggle_builder_track(state, track["id"]), InternalCommand(
                action="builder_toggle_track",
                data={
                    "playlist_id": state.builder.target_playlist_id,
                    "track_id": track["id"],
                    "adding": track["id"] not in state.builder.playlist_track_ids,
                },
            )
        return state, None

    # Play track
    if char == "p" or event_type == "enter":
        track = _get_selected_track(state)
        if track:
            return state, InternalCommand(
                action="builder_play_track",
                data={"track_id": track["id"]},
            )
        return state, None

    # Sort dropdown
    if char == "s":
        return show_builder_sort_dropdown(state), None

    # Filter dropdown
    if char == "f":
        return show_builder_filter_dropdown(state), None

    # Remove last filter
    if char == "d":
        return remove_builder_filter(state), None

    # Clear all filters
    if char == "c":
        return clear_builder_filters(state), None

    # Exit builder
    if event_type == "escape" or char == "q":
        return hide_playlist_builder(state), InternalCommand(
            action="builder_save_and_exit",
            data={
                "playlist_id": state.builder.target_playlist_id,
                "scroll_position": state.builder.selected_index,
                "sort_field": state.builder.sort_field,
                "sort_direction": state.builder.sort_direction,
                "filters": [
                    {"field": f.field, "operator": f.operator, "value": f.value}
                    for f in state.builder.filters
                ],
            },
        )

    return state, None


def _handle_sort_dropdown_key(
    state: UIState,
    event: dict,
) -> tuple[Optional[UIState], Optional[Union[str, InternalCommand]]]:
    """Handle keys in sort dropdown."""
    event_type = event.get("type")
    char = event.get("char", "")

    if event_type == "arrow_down" or char == "j":
        return move_builder_dropdown_selection(state, 1), None

    if event_type == "arrow_up" or char == "k":
        return move_builder_dropdown_selection(state, -1), None

    if event_type == "enter":
        return select_builder_sort_field(state), None

    if event_type == "escape":
        return cancel_builder_dropdown(state), None

    return state, None


def _handle_filter_field_key(
    state: UIState,
    event: dict,
) -> tuple[Optional[UIState], Optional[Union[str, InternalCommand]]]:
    """Handle keys in filter field selection dropdown."""
    event_type = event.get("type")
    char = event.get("char", "")

    if event_type == "arrow_down" or char == "j":
        return move_builder_dropdown_selection(state, 1), None

    if event_type == "arrow_up" or char == "k":
        return move_builder_dropdown_selection(state, -1), None

    if event_type == "enter":
        return select_builder_filter_field(state), None

    if event_type == "escape":
        return cancel_builder_dropdown(state), None

    return state, None


def _handle_filter_operator_key(
    state: UIState,
    event: dict,
) -> tuple[Optional[UIState], Optional[Union[str, InternalCommand]]]:
    """Handle keys in filter operator selection dropdown."""
    event_type = event.get("type")
    char = event.get("char", "")

    if event_type == "arrow_down" or char == "j":
        return move_builder_dropdown_selection(state, 1), None

    if event_type == "arrow_up" or char == "k":
        return move_builder_dropdown_selection(state, -1), None

    if event_type == "enter":
        return select_builder_filter_operator(state), None

    if event_type == "escape":
        return cancel_builder_dropdown(state), None

    return state, None


def _handle_filter_value_key(
    state: UIState,
    event: dict,
) -> tuple[Optional[UIState], Optional[Union[str, InternalCommand]]]:
    """Handle keys in filter value text input."""
    event_type = event.get("type")
    char = event.get("char", "")

    if event_type == "enter":
        return confirm_builder_filter(state), None

    if event_type == "escape":
        return cancel_builder_dropdown(state), None

    if event_type == "backspace":
        return backspace_builder_filter_value(state), None

    # Regular character input
    if event_type == "char" and char and char.isprintable():
        return update_builder_filter_value(state, char), None

    return state, None


def _get_selected_track(state: UIState) -> Optional[dict]:
    """Get currently selected track."""
    if not state.builder.displayed_tracks:
        return None
    idx = state.builder.selected_index
    if 0 <= idx < len(state.builder.displayed_tracks):
        return state.builder.displayed_tracks[idx]
    return None
