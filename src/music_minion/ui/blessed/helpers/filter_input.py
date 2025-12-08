"""Shared filter value input helpers for wizard and playlist builder."""

from blessed import Terminal

from music_minion.core.database import get_unique_genres
from music_minion.ui.blessed.helpers.selection import render_selection_list
from music_minion.ui.blessed.helpers.terminal import write_at


def get_value_options(field: str, operator: str) -> tuple[list[str], list[str]]:
    """Returns (display_options, raw_values). Empty lists = text input mode."""
    if field == "genre" and operator == "equals":
        genres = get_unique_genres()
        return ([f"{g} ({c})" for g, c in genres], [g for g, _ in genres])
    return ([], [])


def render_filter_value_input(
    term: Terminal,
    field: str,
    operator: str,
    current_value: str,
    options: list[str],
    selected_idx: int,
    y: int,
    height: int,
) -> int:
    """Render value step - list selection or text input."""
    if height <= 0:
        return 0

    line_num = 0

    # Instructions
    if line_num < height:
        instruction = f"   Enter value for: {field} {operator}"
        write_at(term, 0, y + line_num, term.white(instruction))
        line_num += 1

    # List selection mode
    if options:
        instruction = "Use ↑↓ to select, Enter to confirm"
        remaining_height = height - line_num
        rendered = render_selection_list(
            term, options, selected_idx, y + line_num, remaining_height, instruction
        )
        line_num += rendered
    # Text input mode
    else:
        if line_num < height:
            value_line = f"   Value: {current_value}_"
            write_at(term, 0, y + line_num, term.cyan(value_line))
            line_num += 1

    return line_num


def handle_filter_value_key(
    event: dict, options: list[str], selected_idx: int, current_value: str
) -> tuple[int, str, bool]:
    """Handle key for value step. Returns (new_idx, new_value, should_save)."""
    event_type = event.get("type")
    char = event.get("char", "")

    # List selection mode
    if options:
        if event_type == "arrow_up":
            new_idx = (selected_idx - 1) % len(options)
            return new_idx, current_value, False
        elif event_type == "arrow_down":
            new_idx = (selected_idx + 1) % len(options)
            return new_idx, current_value, False
        elif event_type == "enter":
            return selected_idx, options[selected_idx], True

    # Text input mode
    else:
        if event_type == "char" and char and char.isprintable():
            return selected_idx, current_value + char, False
        elif event_type == "backspace" and current_value:
            return selected_idx, current_value[:-1], False
        elif event_type == "enter":
            return selected_idx, current_value, True

    return selected_idx, current_value, False
