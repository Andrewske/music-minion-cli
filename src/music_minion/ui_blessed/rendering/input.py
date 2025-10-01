"""Input line rendering functions."""

from blessed import Terminal
from ..state import UIState


def render_input(term: Terminal, state: UIState, y: int) -> None:
    """
    Render input line with cursor.

    Args:
        term: blessed Terminal instance
        state: Current UI state
        y: Y position for input line
    """
    # Draw top border
    border = "─" * (term.width - 2)
    print(term.move_xy(0, y) + term.cyan(f"┌{border}┐"))

    # Draw input line with prompt and text
    prompt = term.green("> ")
    input_text = state.input_text
    cursor = term.bold_white("█")

    # Construct the input line
    input_line = prompt + input_text + cursor

    # Handle long input (horizontal scroll if needed)
    max_width = term.width - 4  # Account for borders and padding
    if len(input_text) + 3 > max_width:  # +3 for "> " and cursor
        # Show only the rightmost portion that fits
        visible_text = input_text[-(max_width - 3):]
        input_line = prompt + visible_text + cursor

    # Draw input line
    padding = " " * max(0, term.width - len(input_text) - 5)
    print(term.move_xy(0, y + 1) + term.cyan("│ ") + prompt + input_text + cursor + padding + term.cyan(" │"))

    # Draw bottom border
    print(term.move_xy(0, y + 2) + term.cyan(f"└{border}┘"))
