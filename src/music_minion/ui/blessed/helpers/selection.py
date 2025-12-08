"""Shared selection list rendering helpers."""

from blessed import Terminal
from .terminal import write_at


def _compute_scroll_window(
    selected_idx: int, total_options: int, visible_rows: int
) -> tuple[int, int]:
    """
    Compute the start and end indices for a scrollable window.

    Ensures the selected item is always visible within the window.

    Args:
        selected_idx: Index of currently selected option
        total_options: Total number of options
        visible_rows: Number of rows available for displaying options

    Returns:
        Tuple of (start_idx, end_idx) for the visible window
    """
    if total_options <= visible_rows:
        # All options fit, no scrolling needed
        return 0, total_options

    # Center the selected item in the window when possible
    half_window = visible_rows // 2
    start_idx = max(0, selected_idx - half_window)
    end_idx = min(total_options, start_idx + visible_rows)

    # Adjust if we're at the end
    if end_idx - start_idx < visible_rows:
        start_idx = max(0, end_idx - visible_rows)

    return start_idx, end_idx


def render_selection_list(
    term: Terminal,
    options: list[str],
    selected_idx: int,
    y: int,
    height: int,
    instruction: str = "",
) -> int:
    """
    Render a list of selectable options with highlighting and scrolling.

    Used by both wizard and playlist builder for field/operator selection.

    Args:
        term: blessed Terminal instance
        options: List of option strings to display
        selected_idx: Index of currently selected option (0-based)
        y: Starting y position
        height: Available height
        instruction: Optional instruction text to show above options

    Returns:
        Number of lines rendered
    """
    if height <= 0:
        return 0

    line_num = 0

    # Show instruction if provided
    if instruction and line_num < height:
        write_at(term, 0, y + line_num, term.white(f"   {instruction}"))
        line_num += 1

    # Calculate available rows for options
    available_rows = height - line_num
    if available_rows <= 0:
        return line_num

    total_options = len(options)
    start_idx, end_idx = _compute_scroll_window(
        selected_idx, total_options, available_rows
    )

    # Show scroll indicator if items above
    if start_idx > 0 and line_num < height:
        write_at(term, 0, y + line_num, term.dim("   ▲ More above"))
        line_num += 1
        available_rows -= 1

    # Render visible options
    visible_options = options[start_idx:end_idx]
    for i, option in enumerate(visible_options):
        if line_num >= height:
            break

        actual_idx = start_idx + i

        # Highlight selected option
        if actual_idx == selected_idx:
            prefix = "   ▶ "
            text = term.bold_green(option)
        else:
            prefix = "     "
            text = term.white(option)

        write_at(term, 0, y + line_num, prefix + text)
        line_num += 1

    # Show scroll indicator if items below
    if end_idx < total_options and line_num < height:
        write_at(term, 0, y + line_num, term.dim("   ▼ More below"))
        line_num += 1

    return line_num
