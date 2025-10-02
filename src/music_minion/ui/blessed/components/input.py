"""Input line rendering functions."""

from blessed import Terminal
from ..state import UIState


def render_input(term: Terminal, state: UIState, y: int) -> None:
    """
    Render input line with cursor and help text.

    Args:
        term: blessed Terminal instance
        state: Current UI state
        y: Y position for input line
    """
    import sys
    from .wizard import get_wizard_footer_text

    # Draw top border
    border = "─" * (term.width - 2)
    sys.stdout.write(term.move_xy(0, y) + term.cyan(f"┌{border}┐"))

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
    sys.stdout.write(term.move_xy(0, y + 1) + term.cyan("│ ") + prompt + input_text + cursor + padding + term.cyan(" │"))

    # Draw bottom border with optional help text
    if state.wizard_active:
        # Show wizard-specific help text
        help_text = get_wizard_footer_text(state)
        # Truncate if too long
        max_help_width = term.width - 4
        if len(help_text) > max_help_width:
            help_text = help_text[:max_help_width - 3] + "..."
        # Center the help text in the border
        padding_left = (term.width - len(help_text) - 2) // 2
        padding_right = term.width - len(help_text) - padding_left - 2
        bottom_border = "─" * padding_left + term.white(help_text) + term.cyan("─" * padding_right)
        sys.stdout.write(term.move_xy(0, y + 2) + term.cyan("└") + bottom_border + term.cyan("┘"))
    else:
        # Normal bottom border
        sys.stdout.write(term.move_xy(0, y + 2) + term.cyan(f"└{border}┘"))
