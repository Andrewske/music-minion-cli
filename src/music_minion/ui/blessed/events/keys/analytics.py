"""Analytics viewer mode keyboard handlers."""

from music_minion.ui.blessed.state import (
    UIState,
    InternalCommand,
    hide_analytics_viewer,
    scroll_analytics_viewer,
)


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
