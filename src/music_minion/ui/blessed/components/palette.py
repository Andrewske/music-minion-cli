"""Command palette rendering functions."""

from blessed import Terminal
from ..state import UIState


def render_palette(term: Terminal, state: UIState, y: int, height: int) -> None:
    """
    Render command palette with scrolling support.

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
    scroll_offset = state.palette_scroll

    # Reserve lines for header and footer
    header_lines = 1
    footer_lines = 1
    content_height = height - header_lines - footer_lines

    line_num = 0

    # Header
    if line_num < height:
        header_text = "   Command Palette"
        sys.stdout.write(term.move_xy(0, y + line_num) + term.bold_cyan(header_text))
        line_num += 1

    # Render commands
    if not filtered_commands:
        if line_num < height:
            sys.stdout.write(term.move_xy(0, y + line_num) + term.white("  No matching commands"))
            line_num += 1
    else:
        # Render items with scroll offset
        items_rendered = 0
        for item_index, (cat, cmd, icon, desc) in enumerate(filtered_commands):
            # Skip items before scroll offset
            if item_index < scroll_offset:
                continue

            # Stop if we've filled the content area
            if items_rendered >= content_height:
                break

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
            items_rendered += 1

    # Clear remaining lines
    while line_num < height - footer_lines:
        sys.stdout.write(term.move_xy(0, y + line_num) + term.clear_eol)
        line_num += 1

    # Footer help text with scroll indicator
    if line_num < height:
        total_items = len(filtered_commands)
        if total_items > content_height:
            current_position = min(selected_index + 1, total_items)
            footer = f"   [{current_position}/{total_items}] ↑↓ navigate  Enter select  Esc cancel"
        else:
            footer = "   ↑↓ navigate  Enter select  Esc cancel"

        sys.stdout.write(term.move_xy(0, y + line_num) + term.white(footer))
        line_num += 1
