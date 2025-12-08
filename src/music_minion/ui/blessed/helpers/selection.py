"""Shared selection list rendering helpers."""

from blessed import Terminal
from .terminal import write_at


def render_selection_list(
    term: Terminal,
    options: list[str],
    selected_idx: int,
    y: int,
    height: int,
    instruction: str = "",
) -> int:
    """
    Render a list of selectable options with highlighting.

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

    # Render options with highlighting
    for i, option in enumerate(options):
        if line_num >= height:
            break

        # Highlight selected option
        if i == selected_idx:
            prefix = "   ▶ "
            text = term.bold_green(option)
        else:
            prefix = "     "
            text = term.white(option)

        write_at(term, 0, y + line_num, prefix + text)
        line_num += 1

    return line_num
