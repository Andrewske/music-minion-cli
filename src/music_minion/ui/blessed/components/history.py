"""Command history rendering functions."""

from blessed import Terminal
from ..state import UIState


def render_history(term: Terminal, state: UIState, y_start: int, height: int) -> None:
    """
    Render scrollable command history.

    Args:
        term: blessed Terminal instance
        state: Current UI state
        y_start: Starting y position
        height: Available height for history
    """
    if height <= 0:
        return

    history = state.history
    scroll_offset = state.history_scroll

    # Calculate visible window based on scroll offset
    # scroll_offset = 0 means showing newest (bottom)
    # scroll_offset > 0 means scrolled up (showing older messages)
    if len(history) <= height:
        # All history fits, show everything
        visible_lines = history
    else:
        # Calculate start and end indices
        # End index is from the bottom, adjusted by scroll offset
        end_idx = len(history) - scroll_offset
        start_idx = max(0, end_idx - height)
        visible_lines = history[start_idx:end_idx]

    # Color mapping
    color_map = {
        'white': term.white,
        'green': term.green,
        'red': term.red,
        'cyan': term.cyan,
        'yellow': term.yellow,
        'blue': term.blue,
        'magenta': term.magenta,
    }

    # Render each line
    for i, (text, color) in enumerate(visible_lines):
        color_func = color_map.get(color, term.white)
        print(term.move_xy(0, y_start + i) + term.clear_eol + color_func(text))

    # Clear any remaining lines in the region
    for i in range(len(visible_lines), height):
        print(term.move_xy(0, y_start + i) + term.clear_eol)

    # Show scroll indicator if scrolled up
    if scroll_offset > 0:
        total_lines = len(history)
        indicator = f"↑ Scrolled ({scroll_offset}/{total_lines} lines from bottom)"
        # Display in top-right corner of history area
        indicator_x = max(0, term.width - len(indicator) - 2)
        print(term.move_xy(indicator_x, y_start) + term.bold_yellow(indicator))
