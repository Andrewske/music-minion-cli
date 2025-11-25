"""Comparison history viewer mode keyboard handlers."""

from music_minion.ui.blessed.state import (
    UIState,
    InternalCommand,
    hide_comparison_history,
    move_comparison_history_selection,
)


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
