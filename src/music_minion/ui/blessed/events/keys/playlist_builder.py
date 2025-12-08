"""Key handler for playlist builder mode."""

from typing import Optional, Union

from music_minion.ui.blessed.state import (
    UIState,
    InternalCommand,
    move_builder_selection,
    show_builder_sort_dropdown,
    move_builder_dropdown_selection,
    select_builder_sort_field,
    toggle_filter_editor_mode,
    move_filter_editor_selection,
    start_editing_filter,
    start_adding_filter,
    advance_filter_editor_step,
    save_filter_editor_changes,
    delete_filter,
    remove_builder_filter,
    clear_builder_filters,
    cancel_builder_dropdown,
    hide_playlist_builder,
    toggle_builder_track,
    replace,
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
    elif builder.filter_editor_mode:
        return _handle_filter_editor_key(state, event)

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
    if event_type == "enter":
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

    # Toggle play/pause
    if char == " ":
        track = _get_selected_track(state)
        return state, InternalCommand(
            action="builder_toggle_playback",
            data={"track_id": track["id"] if track else None},
        )

    # Numeric keys 0-9: Jump to percentage of track
    if event_type == "char" and char and char.isdigit():
        percentage = int(char) * 10
        return state, InternalCommand(
            action="seek_percentage", data={"percentage": percentage}
        )

    # Sort dropdown
    if char == "s":
        return show_builder_sort_dropdown(state), None

    # Toggle filter editor
    if char == "f":
        return toggle_filter_editor_mode(state), None

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


def _handle_filter_editor_key(
    state: UIState,
    event: dict,
) -> tuple[Optional[UIState], Optional[Union[str, InternalCommand]]]:
    """Handle keys in filter editor mode."""
    builder = state.builder
    event_type = event.get("type")
    char = event.get("char", "")

    if builder.filter_editor_editing:
        return _handle_filter_editing_key(state, event)

    # Navigation
    if event_type == "arrow_down" or char == "j":
        return move_filter_editor_selection(state, 1), None

    if event_type == "arrow_up" or char == "k":
        return move_filter_editor_selection(state, -1), None

    # Edit selected filter
    if char == "e":
        selected = builder.filter_editor_selected
        if selected >= 0 and selected < len(builder.filters):
            return start_editing_filter(state, selected), None
        return state, None

    # Delete selected filter
    if char == "d":
        selected = builder.filter_editor_selected
        if selected >= 0 and selected < len(builder.filters):
            return delete_filter(state, selected), None
        return state, None

    # Add new filter
    if char == "a":
        return start_adding_filter(state), None

    # Save and exit
    if event_type == "enter":
        return save_filter_editor_changes(state), None

    # Cancel and exit
    if event_type == "escape":
        return toggle_filter_editor_mode(state), None

    return state, None


def _handle_filter_editing_key(
    state: UIState,
    event: dict,
) -> tuple[Optional[UIState], Optional[Union[str, InternalCommand]]]:
    """Handle keys when editing a filter field/operator/value."""
    event_type = event.get("type")
    char = event.get("char", "")
    step = state.builder.filter_editor_step

    # Cancel editing
    if event_type == "escape":
        return replace(
            state,
            builder=replace(
                state.builder,
                filter_editor_editing=False,
                filter_editor_field=None,
                filter_editor_operator=None,
                filter_editor_value="",
                filter_editor_options=[],
                filter_editor_selected=0,
            ),
        ), None

    # Steps 0 & 1: List navigation with j/k or arrows
    if step in (0, 1):
        # j/k navigation
        if event_type == "key" and char in ("j", "k"):
            delta = 1 if char == "j" else -1
            options = state.builder.filter_editor_options
            if options:
                new_idx = (state.builder.filter_editor_selected + delta) % len(options)
                return replace(
                    state,
                    builder=replace(state.builder, filter_editor_selected=new_idx),
                ), None

        # Arrow key navigation
        elif event_type in ("arrow_down", "arrow_up"):
            delta = 1 if event_type == "arrow_down" else -1
            options = state.builder.filter_editor_options
            if options:
                new_idx = (state.builder.filter_editor_selected + delta) % len(options)
                return replace(
                    state,
                    builder=replace(state.builder, filter_editor_selected=new_idx),
                ), None

        # Enter: Advance to next step
        elif event_type == "enter":
            return advance_filter_editor_step(state), None

    # Step 2: Value input
    elif step == 2:
        if event_type == "char" and char and char.isprintable():
            return replace(
                state,
                builder=replace(
                    state.builder,
                    filter_editor_value=state.builder.filter_editor_value + char,
                ),
            ), None

        elif event_type == "backspace" and state.builder.filter_editor_value:
            return replace(
                state,
                builder=replace(
                    state.builder,
                    filter_editor_value=state.builder.filter_editor_value[:-1],
                ),
            ), None

        elif event_type == "enter":
            # Save and exit editing
            return save_filter_editor_changes(state), None

    return state, None


def _get_selected_track(state: UIState) -> Optional[dict]:
    """Get currently selected track."""
    if not state.builder.displayed_tracks:
        return None
    idx = state.builder.selected_index
    if 0 <= idx < len(state.builder.displayed_tracks):
        return state.builder.displayed_tracks[idx]
    return None
