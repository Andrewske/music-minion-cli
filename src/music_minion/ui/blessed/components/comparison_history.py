"""Comparison history viewer rendering component."""

from datetime import datetime
from typing import Any

from blessed import Terminal

from music_minion.ui.blessed.helpers import write_at
from music_minion.ui.blessed.state import UIState


def render_comparison_history_viewer(
    term: Terminal,
    state: UIState,
    y_start: int,
    height: int,
) -> None:
    """
    Render comparison history viewer with scrollable list.

    Shows recent pairwise comparisons from rate command (Elo system).

    Args:
        term: blessed Terminal instance
        state: Current UI state
        y_start: Starting Y position
        height: Available height
    """
    if height <= 3:  # Need minimum height for header + footer
        return

    comparisons = state.comparison_history_comparisons
    selected = state.comparison_history_selected
    scroll = state.comparison_history_scroll

    line_num = 0

    # Header
    if line_num < height:
        header_text = "   🏆 Comparison History"
        write_at(term, 0, y_start + line_num, term.bold_cyan(header_text))
        line_num += 1

    # Separator
    if line_num < height:
        separator = "   " + "─" * (term.width - 6)
        write_at(term, 0, y_start + line_num, term.white(separator))
        line_num += 1

    # Calculate visible window
    visible_height = height - line_num - 2  # Reserve 2 lines for footer

    if not comparisons:
        # Empty state
        if line_num < height - 2:
            empty_msg = "   No comparisons found. Run 'rate' to start comparing tracks."
            write_at(term, 0, y_start + line_num, term.yellow(empty_msg))
            line_num += 1
    else:
        # Render comparisons list
        end_idx = min(scroll + visible_height, len(comparisons))
        start_idx = scroll
        visible_comparisons = comparisons[start_idx:end_idx]

        for i, comparison in enumerate(visible_comparisons):
            if line_num >= height - 2:
                break

            comparison_idx = start_idx + i
            is_selected = comparison_idx == selected

            # Format comparison line
            comparison_line = _format_comparison_line(comparison, term, is_selected)

            write_at(term, 0, y_start + line_num, comparison_line)
            line_num += 1

    # Clear remaining lines
    while line_num < height - 2:
        write_at(term, 0, y_start + line_num, "")
        line_num += 1

    # Scroll indicator (if scrolled)
    if line_num < height - 1:
        if scroll > 0 or (len(comparisons) > scroll + visible_height):
            indicator = f"   Showing {scroll + 1}-{min(scroll + visible_height, len(comparisons))} of {len(comparisons)}"
            write_at(term, 0, y_start + line_num, term.bright_black(indicator))
        line_num += 1

    # Footer help text
    if line_num < height:
        footer = "   [↑/↓] Navigate  [Esc/Q] Close"
        write_at(term, 0, y_start + line_num, term.white(footer))
        line_num += 1


def _format_comparison_line(
    comparison: dict[str, Any], term: Terminal, is_selected: bool
) -> str:
    """
    Format a single comparison line for display.

    Args:
        comparison: Comparison dictionary with track info
        term: Terminal instance
        is_selected: Whether this comparison is currently selected

    Returns:
        Formatted line string with terminal codes
    """
    # Extract comparison info
    track_a_title = comparison.get("track_a_title", "Unknown")
    track_a_artist = comparison.get("track_a_artist", "Unknown")
    track_b_title = comparison.get("track_b_title", "Unknown")
    track_b_artist = comparison.get("track_b_artist", "Unknown")
    winner_id = comparison.get("winner_id")
    track_a_id = comparison.get("track_a_id")
    track_b_id = comparison.get("track_b_id")
    timestamp = comparison.get("timestamp", "")
    session_id = comparison.get("session_id", "")

    # Format timestamp (show time ago)
    time_str = _format_time_ago(timestamp)

    # Determine winner and format comparison
    if winner_id == track_a_id:
        winner_str = f"{track_a_artist} - {track_a_title}"
        loser_str = f"{track_b_artist} - {track_b_title}"
        icon = "🏆"
    elif winner_id == track_b_id:
        winner_str = f"{track_b_artist} - {track_b_title}"
        loser_str = f"{track_a_artist} - {track_a_title}"
        icon = "🏆"
    else:
        # Shouldn't happen, but handle gracefully
        winner_str = f"{track_a_artist} - {track_a_title}"
        loser_str = f"{track_b_artist} - {track_b_title}"
        icon = "⚖️"

    # Truncate session ID
    session_short = session_id[:8] if session_id else "unknown"

    # Selection indicator
    if is_selected:
        prefix = "  > "
        color_func = term.bold_cyan
    else:
        prefix = "    "
        color_func = term.white

    # Truncate track names to fit terminal width
    # Reserve space for: prefix(4) + icon(2) + " > "(3) + " • "(3) + time(8) + " • Session: "(12) + session(8) = 40
    max_track_width = (
        term.width - 50
    ) // 2  # Split remaining space between winner and loser
    if len(winner_str) > max_track_width:
        winner_str = winner_str[: max_track_width - 3] + "..."
    if len(loser_str) > max_track_width:
        loser_str = loser_str[: max_track_width - 3] + "..."

    # Build line: "  > 🏆 Winner > Loser • 2h ago • Session: abc12345"
    line = f"{prefix}{icon} {winner_str} > {loser_str} • {time_str} • Session: {session_short}"

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
