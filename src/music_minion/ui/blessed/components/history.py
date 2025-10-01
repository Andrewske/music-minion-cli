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

    # Get the last N lines that fit in the available height
    history = state.history
    visible_lines = history[-height:] if len(history) > height else history

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
        print(term.move_xy(0, y_start + i) + color_func(text))

    # Clear any remaining lines in the region
    for i in range(len(visible_lines), height):
        print(term.move_xy(0, y_start + i) + term.clear_eol)
