"""Playlist builder component for blessed UI."""

from blessed import Terminal

from ..helpers import write_at
from ..state import UIState


def render_playlist_builder(
    term: Terminal,
    state: UIState,
    y: int,
    height: int,
) -> int:
    """Render the playlist builder overlay.

    Args:
        term: Terminal instance
        state: UI state with builder data
        y: Starting Y position
        height: Available height

    Returns:
        Height used
    """
    builder = state.builder

    # Calculate layout
    header_height = 2  # Title + sort/filter info
    footer_height = 1  # Help text
    list_height = height - header_height - footer_height

    current_y = y

    # Render header
    current_y = _render_header(term, builder, current_y)

    # Render track list
    current_y = _render_track_list(term, builder, current_y, list_height)

    # Render footer
    current_y = _render_footer(term, builder, current_y)

    # Render dropdown overlay if active
    if builder.dropdown_mode:
        _render_dropdown(term, builder, y + 2)  # Position below header

    return height


def _render_header(term: Terminal, builder, y: int) -> int:
    """Render header with playlist name and sort/filter info."""
    # Title line
    title = f"   🔨 Building: \"{builder.target_playlist_name}\""
    write_at(term, 0, y, term.bold(title))

    # Sort/filter info line
    direction_symbol = "A→Z" if builder.sort_direction == "asc" else "Z→A"
    if builder.sort_field in {"year", "bpm"}:
        direction_symbol = "↑" if builder.sort_direction == "asc" else "↓"

    sort_info = f"Sort: {builder.sort_field.title()} ({direction_symbol})"

    filter_parts = []
    for f in builder.filters:
        op_display = {
            "contains": "~",
            "equals": "=",
            "not_equals": "!=",
            "starts_with": "^",
            "ends_with": "$",
            "gt": ">",
            "lt": "<",
            "gte": ">=",
            "lte": "<=",
        }.get(f.operator, f.operator)
        filter_parts.append(f'{f.field} {op_display} "{f.value}"')

    filter_info = " | Filters: " + ", ".join(filter_parts) if filter_parts else ""

    info_line = f"   {sort_info}{filter_info}"
    write_at(term, 0, y + 1, term.dim(info_line[:term.width - 1]))

    return y + 2


def _render_track_list(term: Terminal, builder, y: int, height: int) -> int:
    """Render scrollable track list."""
    tracks = builder.displayed_tracks
    selected = builder.selected_index
    scroll = builder.scroll_offset
    in_playlist = builder.playlist_track_ids

    # Calculate visible range
    visible_end = min(scroll + height, len(tracks))

    for i, row_y in enumerate(range(y, y + height)):
        track_idx = scroll + i

        if track_idx >= len(tracks):
            # Clear empty rows
            write_at(term, 0, row_y, "")
            continue

        track = tracks[track_idx]
        is_selected = track_idx == selected
        is_in_playlist = track.get("id") in in_playlist

        # Build track line
        # Star indicator (3 chars)
        star = " ⭐ " if is_in_playlist else "    "

        # Track number (4 chars)
        num = f"{track_idx + 1:3d}."

        # Artist - Title
        artist = track.get("artist", "Unknown")[:20]
        title = track.get("title", "Unknown")[:30]
        main_text = f"{artist} - {title}"

        # Year and BPM (right side)
        year = track.get("year", "")
        bpm = track.get("bpm", "")
        right_info = ""
        if year:
            right_info += f" | {year}"
        if bpm:
            right_info += f" | {int(bpm)} BPM"

        # Calculate available width
        prefix_width = len(star) + len(num) + 1  # star + num + space
        right_width = len(right_info)
        main_width = term.width - prefix_width - right_width - 2

        # Truncate main text
        if len(main_text) > main_width:
            main_text = main_text[:main_width - 1] + "…"
        else:
            main_text = main_text.ljust(main_width)

        # Build full line
        line = f"{star}{num} {main_text}{right_info}"

        # Apply highlighting
        if is_selected:
            line = term.black_on_cyan(line.ljust(term.width))
        else:
            line = line.ljust(term.width)

        write_at(term, 0, row_y, line, clear=False)

    return y + height


def _render_footer(term: Terminal, builder, y: int) -> int:
    """Render footer with position and help text."""
    total = len(builder.displayed_tracks)
    pos = builder.selected_index + 1 if total > 0 else 0

    position_text = f"[{pos}/{total}]"
    help_text = "j/k nav  Space toggle  p play  s sort  f filter  d del filter  Esc exit"

    footer = f"   {position_text} {help_text}"
    write_at(term, 0, y, term.dim(footer[:term.width - 1]))

    return y + 1


def _render_dropdown(term: Terminal, builder, y: int) -> None:
    """Render dropdown overlay for sort/filter selection."""
    mode = builder.dropdown_mode
    options = builder.dropdown_options
    selected = builder.dropdown_selected

    # Dropdown title
    if mode == "sort":
        title = "Sort by:"
    elif mode == "filter_field":
        title = "Filter by:"
    elif mode == "filter_operator":
        title = f"{builder.pending_filter_field}:"
    elif mode == "filter_value":
        title = f"{builder.pending_filter_field} {builder.pending_filter_operator}:"
    else:
        return

    # Calculate dropdown dimensions
    dropdown_width = 25
    dropdown_x = 2

    # Render dropdown box
    write_at(term, dropdown_x, y, term.reverse(f" {title.ljust(dropdown_width - 1)}"))

    if mode == "filter_value":
        # Text input mode
        input_text = builder.filter_value_input + "_"
        write_at(term, dropdown_x, y + 1, term.reverse(f" {input_text.ljust(dropdown_width - 1)}"))
        write_at(term, dropdown_x, y + 2, term.dim(" Enter=confirm  Esc=cancel"))
    else:
        # Option list mode
        for i, option in enumerate(options):
            option_y = y + 1 + i
            prefix = ">" if i == selected else " "
            display = f"{prefix} {option}"

            if i == selected:
                display = term.black_on_white(display.ljust(dropdown_width))
            else:
                display = term.reverse(display.ljust(dropdown_width))

            write_at(term, dropdown_x, option_y, display, clear=False)

        # Help text below options
        help_y = y + 1 + len(options)
        write_at(term, dropdown_x, help_y, term.dim(" j/k select  Enter=confirm  Esc=cancel"))
