"""Pure helper functions for scrolling and selection in list-based UI components."""


def calculate_scroll_offset(
    selected: int,
    current_scroll: int,
    visible_items: int,
    total_items: int,
) -> int:
    """Calculate scroll offset to keep selected item visible in viewport.

    Ensures the selected item remains within the visible viewport by adjusting
    the scroll offset when the selection moves outside the visible range.

    Args:
        selected: Index of the currently selected item (0-based)
        current_scroll: Current scroll offset (0-based)
        visible_items: Number of items visible in the viewport
        total_items: Total number of items in the list

    Returns:
        New scroll offset to keep selected item visible

    Examples:
        >>> # Selection below viewport - scroll down
        >>> calculate_scroll_offset(
        ...     selected=15, current_scroll=0, visible_items=10, total_items=20
        ... )
        6  # Shows items 6-15, selection at bottom of viewport

        >>> # Selection above viewport - scroll up
        >>> calculate_scroll_offset(
        ...     selected=2, current_scroll=10, visible_items=10, total_items=20
        ... )
        2  # Shows items 2-11, selection at top of viewport

        >>> # Selection within viewport - no change
        >>> calculate_scroll_offset(
        ...     selected=5, current_scroll=0, visible_items=10, total_items=20
        ... )
        0  # No scroll change needed
    """
    # Scroll down if selection goes below visible area
    if selected >= current_scroll + visible_items:
        return selected - visible_items + 1

    # Scroll up if selection goes above visible area
    elif selected < current_scroll:
        return selected

    # Selection within visible range - no scroll change
    return current_scroll


def move_selection(
    current: int,
    delta: int,
    total_items: int,
    wrap: bool = True,
) -> int:
    """Move selection by delta with optional wrapping.

    Moves the current selection index by the specified delta, with support for
    circular wrapping (end to start, start to end) or clamping to valid range.

    Args:
        current: Current selection index (0-based)
        delta: Amount to move (-1 for up, +1 for down)
        total_items: Total number of items in the list
        wrap: If True, wrap around at boundaries; if False, clamp to range

    Returns:
        New selection index

    Examples:
        >>> # Move down with wrapping
        >>> move_selection(current=9, delta=1, total_items=10, wrap=True)
        0  # Wraps from last to first

        >>> # Move up with wrapping
        >>> move_selection(current=0, delta=-1, total_items=10, wrap=True)
        9  # Wraps from first to last

        >>> # Move down without wrapping
        >>> move_selection(current=9, delta=1, total_items=10, wrap=False)
        9  # Clamped at last item

        >>> # Normal movement
        >>> move_selection(current=5, delta=1, total_items=10, wrap=True)
        6
    """
    if total_items == 0:
        return 0

    if wrap:
        # Use modulo for circular wrapping
        return (current + delta) % total_items
    else:
        # Clamp to valid range [0, total_items - 1]
        return max(0, min(current + delta, total_items - 1))


def clamp_selection(selection: int, total_items: int) -> int:
    """Clamp selection to valid range [0, total_items - 1].

    Ensures a selection index is within the valid range for a list.
    Useful after list size changes (filtering, data updates).

    Args:
        selection: Selection index to clamp
        total_items: Total number of items in the list

    Returns:
        Clamped selection index

    Examples:
        >>> # Selection beyond end
        >>> clamp_selection(selection=15, total_items=10)
        9  # Clamped to last valid index

        >>> # Negative selection
        >>> clamp_selection(selection=-5, total_items=10)
        0  # Clamped to first index

        >>> # Valid selection
        >>> clamp_selection(selection=5, total_items=10)
        5  # No change

        >>> # Empty list
        >>> clamp_selection(selection=5, total_items=0)
        0
    """
    if total_items == 0:
        return 0
    return max(0, min(selection, total_items - 1))
