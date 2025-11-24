"""Rating history viewer rendering component."""

import sys
from datetime import datetime
from typing import Any

from blessed import Terminal

from music_minion.ui.blessed.state import UIState


def render_rating_history_viewer(
    term: Terminal,
    state: UIState,
    y_start: int,
    height: int,
) -> None:
    """
    Render rating history viewer with scrollable list.

    Shows recent ratings with track info and allows deletion via keyboard.

    Args:
        term: blessed Terminal instance
        state: Current UI state
        y_start: Starting Y position
        height: Available height
    """
    if height <= 3:  # Need minimum height for header + footer
        return

    ratings = state.rating_history_ratings
    selected = state.rating_history_selected
    scroll = state.rating_history_scroll

    line_num = 0

    # Header
    if line_num < height:
        header_text = "   📋 Rating History"
        sys.stdout.write(
            term.move_xy(0, y_start + line_num) + term.bold_cyan(header_text)
        )
        line_num += 1

    # Separator
    if line_num < height:
        separator = "   " + "─" * (term.width - 6)
        sys.stdout.write(term.move_xy(0, y_start + line_num) + term.white(separator))
        line_num += 1

    # Calculate visible window
    visible_height = height - line_num - 2  # Reserve 2 lines for footer

    if not ratings:
        # Empty state
        if line_num < height - 2:
            empty_msg = "   No ratings found."
            sys.stdout.write(
                term.move_xy(0, y_start + line_num) + term.yellow(empty_msg)
            )
            line_num += 1
    else:
        # Render ratings list
        end_idx = min(scroll + visible_height, len(ratings))
        start_idx = scroll
        visible_ratings = ratings[start_idx:end_idx]

        for i, rating in enumerate(visible_ratings):
            if line_num >= height - 2:
                break

            rating_idx = start_idx + i
            is_selected = rating_idx == selected

            # Format rating line
            rating_line = _format_rating_line(rating, term, is_selected)

            sys.stdout.write(term.move_xy(0, y_start + line_num) + rating_line)
            line_num += 1

    # Clear remaining lines
    while line_num < height - 2:
        sys.stdout.write(term.move_xy(0, y_start + line_num) + term.clear_eol)
        line_num += 1

    # Scroll indicator (if scrolled)
    if line_num < height - 1:
        if scroll > 0 or (len(ratings) > scroll + visible_height):
            indicator = f"   Showing {scroll + 1}-{min(scroll + visible_height, len(ratings))} of {len(ratings)}"
            sys.stdout.write(
                term.move_xy(0, y_start + line_num) + term.bright_black(indicator)
            )
        line_num += 1

    # Footer help text
    if line_num < height:
        footer = "   [↑/↓] Navigate  [Delete/X] Remove Rating  [Esc/Q] Close"
        sys.stdout.write(term.move_xy(0, y_start + line_num) + term.white(footer))
        line_num += 1


def _format_rating_line(
    rating: dict[str, Any], term: Terminal, is_selected: bool
) -> str:
    """
    Format a single rating line for display.

    Args:
        rating: Rating dictionary with track info
        term: Terminal instance
        is_selected: Whether this rating is currently selected

    Returns:
        Formatted line string with terminal codes
    """
    # Extract rating info
    rating_type = rating.get("rating_type", "unknown")
    timestamp = rating.get("timestamp", "")
    artist = rating.get("artist", "Unknown")
    title = rating.get("title", "Unknown")
    source = rating.get("source", "user")

    # Format timestamp (show time ago)
    time_str = _format_time_ago(timestamp)

    # Rating type icon
    type_icons = {
        "like": "👍",
        "love": "❤️",
        "archive": "📦",
        "skip": "⏭️",
    }
    icon = type_icons.get(rating_type, "⭐")

    # Source indicator
    source_indicators = {
        "user": "",
        "soundcloud": " [SC]",
        "spotify": " [SP]",
        "youtube": " [YT]",
    }
    source_str = source_indicators.get(source, "")

    # Build line
    # Format: "  > 👍 like  • Artist - Title • 2h ago [SC]"
    # Or:     "    👍 like  • Artist - Title • 2h ago"

    # Selection indicator
    if is_selected:
        prefix = "  > "
        color_func = term.bold_cyan
    else:
        prefix = "    "
        color_func = term.white

    # Truncate artist/title to fit terminal width
    max_track_width = term.width - 40  # Reserve space for icon, type, time, source
    track_str = f"{artist} - {title}"
    if len(track_str) > max_track_width:
        track_str = track_str[: max_track_width - 3] + "..."

    # Build line components
    type_str = f"{icon} {rating_type}"
    line = f"{prefix}{type_str}  • {track_str} • {time_str}{source_str}"

    # Ensure line doesn't overflow terminal
    if len(line) > term.width - 1:
        line = line[: term.width - 4] + "..."

    return term.clear_eol + color_func(line)


def _format_time_ago(timestamp_str: str) -> str:
    """
    Format timestamp as relative time ago (e.g., '2h ago', '3d ago').

    Args:
        timestamp_str: ISO format timestamp string

    Returns:
        Formatted relative time string
    """
    try:
        timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        now = datetime.now(timestamp.tzinfo) if timestamp.tzinfo else datetime.now()
        delta = now - timestamp

        # Calculate relative time
        seconds = delta.total_seconds()
        if seconds < 60:
            return "just now"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            return f"{minutes}m ago"
        elif seconds < 86400:
            hours = int(seconds / 3600)
            return f"{hours}h ago"
        elif seconds < 604800:
            days = int(seconds / 86400)
            return f"{days}d ago"
        elif seconds < 2592000:
            weeks = int(seconds / 604800)
            return f"{weeks}w ago"
        else:
            months = int(seconds / 2592000)
            return f"{months}mo ago"
    except (ValueError, AttributeError):
        # If parsing fails, return raw timestamp
        return timestamp_str[:10]  # Just show date part
