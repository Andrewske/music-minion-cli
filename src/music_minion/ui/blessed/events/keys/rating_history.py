"""Rating history viewer mode keyboard handlers."""

from music_minion.ui.blessed.state import (
    UIState,
    InternalCommand,
    hide_rating_history,
    move_rating_history_selection,
    delete_rating_history_item,
)
from music_minion.core import database


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
            selected_rating = state.rating_history_ratings[
                state.rating_history_selected
            ]
            rating_id = selected_rating.get("rating_id")

            if rating_id:
                # Delete from database and update state
                if database.delete_rating_by_id(rating_id):
                    # Remove from UI list
                    state = delete_rating_history_item(
                        state, state.rating_history_selected
                    )

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
