"""Command palette rendering functions."""

from blessed import Terminal
from ..state import UIState


def render_palette(term: Terminal, state: UIState, y: int, height: int) -> None:
    """
    Render command palette.

    Args:
        term: blessed Terminal instance
        state: Current UI state
        y: Starting y position
        height: Available height for palette
    """
    import sys

    if not state.palette_visible or height <= 0:
        return

    filtered_commands = state.palette_items
    selected_index = state.palette_selected

    # Reserve lines for header and footer
    header_lines = 1
    footer_lines = 1
    content_height = height - header_lines - footer_lines

    line_num = 0

    # Header
    if line_num < height:
        header_text = "   🎵 Playback"
        sys.stdout.write(term.move_xy(0, y + line_num) + term.bold_cyan(header_text))
        line_num += 1

    # Render commands
    if not filtered_commands:
        if line_num < height:
            sys.stdout.write(term.move_xy(0, y + line_num) + term.white("  No matching commands"))
            line_num += 1
    else:
        current_category = None
        item_index = 0

        for cat, cmd, icon, desc in filtered_commands:
            if line_num >= height - footer_lines:
                break

            # Add category header if new category
            if cat != current_category:
                if current_category is not None and line_num < height - footer_lines:
                    # Add spacing between categories
                    sys.stdout.write(term.move_xy(0, y + line_num) + term.clear_eol)
                    line_num += 1
                    if line_num >= height - footer_lines:
                        break

                if line_num < height - footer_lines:
                    sys.stdout.write(term.move_xy(0, y + line_num) + term.bold_cyan(cat))
                    line_num += 1
                    current_category = cat

            if line_num >= height - footer_lines:
                break

            # Create command item with highlighting
            is_selected = item_index == selected_index
            cmd_text = f"{cmd:<20}"

            if is_selected:
                # Selected item: highlighted background
                item_line = (
                    term.black_on_cyan(f"  {icon} ") +
                    term.black_on_cyan(cmd_text) +
                    term.black_on_cyan(f" {desc}")
                )
            else:
                # Normal item
                item_line = (
                    term.bold(f"  {icon} ") +
                    term.cyan(cmd_text) +
                    term.white(f" {desc}")
                )

            sys.stdout.write(term.move_xy(0, y + line_num) + item_line)
            line_num += 1
            item_index += 1

    # Clear remaining lines
    while line_num < height - footer_lines:
        sys.stdout.write(term.move_xy(0, y + line_num) + term.clear_eol)
        line_num += 1

    # Footer help text
    if line_num < height:
        footer = "   ↑↓ navigate  Enter select  Esc cancel"
        sys.stdout.write(term.move_xy(0, y + line_num) + term.white(footer))
        line_num += 1
