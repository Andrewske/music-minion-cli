"""Command palette rendering functions."""

from blessed import Terminal
from ..state import UIState


def load_playlist_items() -> list[tuple[str, str, str, str]]:
    """
    Load playlists from database and convert to palette items format.

    Returns:
        List of palette items: (category, name, icon, description)
    """
    # Import here to avoid circular dependencies
    from ....domain.playlists import crud as playlists

    all_playlists = playlists.get_playlists_sorted_by_recent()
    active = playlists.get_active_playlist()
    active_id = active['id'] if active else None

    items = []
    for pl in all_playlists:
        # Determine category and icon
        category = pl['type'].capitalize()
        icon = "★" if pl['id'] == active_id else "◦"

        # Build description with track count and type
        track_count = pl.get('track_count', 0)
        desc = f"{track_count} tracks"
        if pl['type'] == 'smart':
            desc = f"Smart • {desc}"

        # Add active indicator to description if active
        if pl['id'] == active_id:
            desc = f"ACTIVE • {desc}"

        items.append((category, pl['name'], icon, desc))

    return items


def filter_playlist_items(query: str, items: list[tuple[str, str, str, str]]) -> list[tuple[str, str, str, str]]:
    """
    Filter playlist items by name (case-insensitive substring match).

    Args:
        query: Search query string
        items: List of playlist items to filter

    Returns:
        Filtered list of items matching query
    """
    if not query:
        return items

    query_lower = query.lower()
    filtered = []
    for item in items:
        cat, name, icon, desc = item
        # Match against playlist name (case-insensitive)
        if query_lower in name.lower():
            filtered.append(item)

    return filtered


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

    # Header - different based on palette mode
    if line_num < height:
        if state.palette_mode == 'playlist':
            header_text = "   📋 Select Playlist"
        else:
            header_text = "   Command Palette"
        sys.stdout.write(term.move_xy(0, y + line_num) + term.bold_cyan(header_text))
        line_num += 1

    # Render items
    if not filtered_commands:
        if line_num < height:
            empty_msg = "  No playlists found" if state.palette_mode == 'playlist' else "  No matching commands"
            sys.stdout.write(term.move_xy(0, y + line_num) + term.white(empty_msg))
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

    # Footer help text - confirmation or normal mode
    if line_num < height:
        if state.confirmation_active and state.confirmation_type == 'delete_playlist':
            # Show confirmation prompt
            playlist_name = state.confirmation_data.get('playlist_name', 'Unknown')
            footer = f"   Delete '{playlist_name}'? [Enter/Y]es / [N]o"
            sys.stdout.write(term.move_xy(0, y + line_num) + term.yellow(footer))
        else:
            # Normal footer with scroll indicator and help text
            total_items = len(filtered_commands)
            if state.palette_mode == 'playlist':
                # Playlist mode footer with delete key help
                if total_items > content_height:
                    current_position = min(selected_index + 1, total_items)
                    footer = f"   [{current_position}/{total_items}] ↑↓ navigate  Enter select  Del delete  Esc cancel"
                else:
                    footer = "   ↑↓ navigate  Enter select  Del delete  Esc cancel"
            else:
                # Command mode footer
                if total_items > content_height:
                    current_position = min(selected_index + 1, total_items)
                    footer = f"   [{current_position}/{total_items}] ↑↓ navigate  Enter select  Esc cancel"
                else:
                    footer = "   ↑↓ navigate  Enter select  Esc cancel"

            sys.stdout.write(term.move_xy(0, y + line_num) + term.white(footer))
        line_num += 1
