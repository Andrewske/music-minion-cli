"""Input line rendering functions."""

from blessed import Terminal

from ..helpers import write_at
from ..state import UIState


def _scroll_window(text: str, cursor_pos: int, width: int) -> tuple[str, int]:
    """Return (visible_text, visible_cursor) scrolled to keep cursor in view.

    width is the number of character cells available for the text + block cursor.
    """
    if len(text) < width:
        return text, cursor_pos
    # Keep cursor within the window; bias so the cursor stays one cell from edge.
    start = max(0, cursor_pos - width + 1)
    return text[start : start + width], cursor_pos - start


def _render_input_line(term: Terminal, state: UIState) -> str:
    """Build the bordered input line with a block cursor at cursor_pos."""
    prompt_plain = "> "
    text = state.input_text
    cursor_pos = max(0, min(state.cursor_pos, len(text)))

    # Available cells between "│ > " and " │" borders.
    avail = max(1, term.width - 4 - len(prompt_plain))
    visible, vis_cursor = _scroll_window(text, cursor_pos, avail)

    before = visible[:vis_cursor]
    cursor_char = visible[vis_cursor] if vis_cursor < len(visible) else " "
    after = visible[vis_cursor + 1 :] if vis_cursor < len(visible) else ""

    rendered = (
        term.green(prompt_plain)
        + before
        + term.reverse(cursor_char)
        + after
    )
    used = len(prompt_plain) + len(before) + 1 + len(after)
    padding = " " * max(0, term.width - 4 - used)
    return term.cyan("│ ") + rendered + padding + term.cyan(" │")


def render_input(term: Terminal, state: UIState, y: int) -> None:
    """
    Render input line with cursor and help text.

    Args:
        term: blessed Terminal instance
        state: Current UI state
        y: Y position for input line
    """
    from .wizard import get_wizard_footer_text

    # Draw top border
    border = "─" * (term.width - 2)
    write_at(term, 0, y, term.cyan(f"┌{border}┐"))

    # Render input line: prompt + before-cursor + cursor + after-cursor.
    # Horizontal scroll keeps the cursor visible inside the available width.
    write_at(term, 0, y + 1, _render_input_line(term, state))

    # Draw bottom border with optional help text
    if state.wizard_active:
        # Show wizard-specific help text
        help_text = get_wizard_footer_text(state)
        # Truncate if too long
        max_help_width = term.width - 4
        if len(help_text) > max_help_width:
            help_text = help_text[: max_help_width - 3] + "..."
        # Center the help text in the border
        padding_left = (term.width - len(help_text) - 2) // 2
        padding_right = term.width - len(help_text) - padding_left - 2
        bottom_border = (
            "─" * padding_left + term.white(help_text) + term.cyan("─" * padding_right)
        )
        write_at(term, 0, y + 2, term.cyan("└") + bottom_border + term.cyan("┘"))
    else:
        # Normal bottom border
        write_at(term, 0, y + 2, term.cyan(f"└{border}┘"))
