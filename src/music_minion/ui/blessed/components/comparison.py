"""Comparison mode overlay rendering component."""

import sys
from typing import Any

from blessed import Terminal

from music_minion.ui.blessed.state import ComparisonState


def render_comparison_overlay(
    term: Terminal,
    comparison: ComparisonState,
    player_state: Any,
    layout: dict[str, int],
) -> None:
    """
    Render comparison mode overlay in command palette area.

    Shows two tracks side-by-side with:
    - Highlighted track has different color/border
    - Ratings and comparison counts
    - Currently playing indicator
    - Session progress
    - Filter info (if applicable)
    - Keyboard shortcuts help

    Args:
        term: blessed Terminal instance
        comparison: Comparison state
        player_state: PlayerState (for currently playing track)
        layout: Layout dictionary with positions and heights
    """
    from loguru import logger

    if not comparison.active:
        logger.info("Comparison not active, returning")
        return

    y = layout.get("palette_y", 0)
    height = layout.get("palette_height", 0)

    if height <= 0:
        logger.info("Height <= 0, returning")
        return

    # Check if in loading state - show skeleton UI
    if comparison.loading:
        _render_loading_skeleton(term, comparison, y, height)
        return

    line_num = 0

    # Header
    if line_num < height:
        header_text = "   🎵 Track Comparison"
        sys.stdout.write(term.move_xy(0, y + line_num) + term.bold_cyan(header_text))
        line_num += 1

    # Separator
    if line_num < height:
        sys.stdout.write(term.move_xy(0, y + line_num) + term.white("   " + "─" * 60))
        line_num += 1

    # Calculate rating info for both tracks
    rating_a = _get_rating_info(comparison.track_a)
    rating_b = _get_rating_info(comparison.track_b)

    # Determine which track is currently playing
    current_track_id = player_state.current_track_id if player_state else None
    is_playing_a = (
        comparison.track_a
        and comparison.track_a.get("id") == current_track_id
        and player_state
        and player_state.is_playing
    )
    is_playing_b = (
        comparison.track_b
        and comparison.track_b.get("id") == current_track_id
        and player_state
        and player_state.is_playing
    )

    # Render Track A and Track B side-by-side
    # Calculate center position for divider
    center_col = term.width // 2

    # Render both tracks (they render on the same lines, split by column)
    if comparison.track_a and comparison.track_b:
        lines_used = _render_tracks_side_by_side(
            term,
            comparison.track_a,
            comparison.track_b,
            rating_a,
            rating_b,
            y + line_num,
            height - line_num - 3,  # Reserve 3 lines for footer
            comparison.highlighted == "a",
            comparison.highlighted == "b",
            is_playing_a,
            is_playing_b,
            center_col,
        )
        line_num += lines_used

    # Session progress and filter info
    progress_lines = render_session_progress(term, comparison, y + line_num, height)
    line_num += progress_lines

    # Clear remaining lines
    while line_num < height - 1:
        sys.stdout.write(term.move_xy(0, y + line_num) + term.clear_eol)
        line_num += 1

    # Footer help text
    if line_num < height:
        footer = "   [←/→] Select  [Space] Play  [Enter] Choose  [A] Archive  [Esc] Exit"
        sys.stdout.write(term.move_xy(0, y + line_num) + term.white(footer))
        line_num += 1


def _render_tracks_side_by_side(
    term: Terminal,
    track_a: dict[str, Any],
    track_b: dict[str, Any],
    rating_a: dict[str, Any],
    rating_b: dict[str, Any],
    y: int,
    max_height: int,
    is_highlighted_a: bool,
    is_highlighted_b: bool,
    is_playing_a: bool,
    is_playing_b: bool,
    center_col: int,
) -> int:
    """
    Render two tracks side-by-side with vertical divider.

    Args:
        term: Terminal instance
        track_a: Track A dictionary
        track_b: Track B dictionary
        rating_a: Rating info for track A
        rating_b: Rating info for track B
        y: Starting Y position
        max_height: Maximum height available
        is_highlighted_a: Whether track A is highlighted
        is_highlighted_b: Whether track B is highlighted
        is_playing_a: Whether track A is currently playing
        is_playing_b: Whether track B is currently playing
        center_col: Column position for center divider

    Returns:
        Number of lines used
    """
    line_num = 0

    # Track headers with selection indicators
    if line_num < max_height:
        # Track A header
        if is_highlighted_a:
            header_a = "[←] Track A"
            header_a_text = term.bold_cyan(header_a)
        else:
            header_a = "[←] Track A"
            header_a_text = term.white(header_a)

        # Track B header
        if is_highlighted_b:
            header_b = "[→] Track B"
            header_b_text = term.bold_cyan(header_b)
        else:
            header_b = "[→] Track B"
            header_b_text = term.white(header_b)

        # Render headers with divider
        sys.stdout.write(
            term.move_xy(2, y + line_num)
            + header_a_text
            + term.move_xy(center_col, y + line_num)
            + term.white("│")
            + term.move_xy(center_col + 2, y + line_num)
            + header_b_text
        )
        line_num += 1

    # Artist names
    if line_num < max_height:
        # Clear the line first to remove any leftover placeholder text
        sys.stdout.write(term.move_xy(0, y + line_num) + term.clear_eol)

        artist_a = track_a.get("artist") or "Unknown"
        artist_b = track_b.get("artist") or "Unknown"

        # Truncate to fit in half-width
        max_width_a = center_col - 4
        max_width_b = center_col - 4

        if len(artist_a) > max_width_a:
            artist_a = artist_a[: max_width_a - 3] + "..."
        if len(artist_b) > max_width_b:
            artist_b = artist_b[: max_width_b - 3] + "..."

        # Apply highlighting
        if is_highlighted_a:
            artist_a_text = term.bold_cyan(artist_a)
        else:
            artist_a_text = term.cyan(artist_a)

        if is_highlighted_b:
            artist_b_text = term.bold_cyan(artist_b)
        else:
            artist_b_text = term.cyan(artist_b)

        sys.stdout.write(
            term.move_xy(2, y + line_num)
            + artist_a_text
            + term.move_xy(center_col, y + line_num)
            + term.white("│")
            + term.move_xy(center_col + 2, y + line_num)
            + artist_b_text
        )
        line_num += 1

    # Title
    if line_num < max_height:
        # Clear the line first to remove any leftover placeholder text
        sys.stdout.write(term.move_xy(0, y + line_num) + term.clear_eol)

        title_a = track_a.get("title") or "Unknown"
        title_b = track_b.get("title") or "Unknown"

        # Truncate to fit
        max_width_a = center_col - 4
        max_width_b = center_col - 4

        if len(title_a) > max_width_a:
            title_a = title_a[: max_width_a - 3] + "..."
        if len(title_b) > max_width_b:
            title_b = title_b[: max_width_b - 3] + "..."

        # Apply highlighting - use cyan for highlighted track
        if is_highlighted_a:
            title_a_text = term.bold_cyan(title_a)
        else:
            title_a_text = term.white(title_a)

        if is_highlighted_b:
            title_b_text = term.bold_cyan(title_b)
        else:
            title_b_text = term.white(title_b)

        sys.stdout.write(
            term.move_xy(2, y + line_num)
            + title_a_text
            + term.move_xy(center_col, y + line_num)
            + term.white("│")
            + term.move_xy(center_col + 2, y + line_num)
            + title_b_text
        )
        line_num += 1

    # Album and year
    if line_num < max_height:
        album_a = track_a.get("album") or ""
        year_a = track_a.get("year")
        info_a = (
            f"{album_a} • {year_a}"
            if album_a and year_a
            else album_a or str(year_a)
            if year_a
            else ""
        )

        album_b = track_b.get("album") or ""
        year_b = track_b.get("year")
        info_b = (
            f"{album_b} • {year_b}"
            if album_b and year_b
            else album_b or str(year_b)
            if year_b
            else ""
        )

        # Truncate to fit
        max_width_a = center_col - 4
        max_width_b = center_col - 4

        if len(info_a) > max_width_a:
            info_a = info_a[: max_width_a - 3] + "..."
        if len(info_b) > max_width_b:
            info_b = info_b[: max_width_b - 3] + "..."

        # Apply highlighting - use cyan for highlighted track
        if is_highlighted_a:
            info_a_text = term.bold_cyan(info_a) if info_a else ""
        else:
            info_a_text = term.white(info_a) if info_a else ""

        if is_highlighted_b:
            info_b_text = term.bold_cyan(info_b) if info_b else ""
        else:
            info_b_text = term.white(info_b) if info_b else ""

        if info_a or info_b:
            # Clear the line first to remove any leftover placeholder text
            sys.stdout.write(term.move_xy(0, y + line_num) + term.clear_eol)

            sys.stdout.write(
                term.move_xy(2, y + line_num)
                + info_a_text
                + term.move_xy(center_col, y + line_num)
                + term.white("│")
                + term.move_xy(center_col + 2, y + line_num)
                + info_b_text
            )
            line_num += 1

    # Ratings
    if line_num < max_height:
        # Clear the line first to remove any leftover placeholder text
        sys.stdout.write(term.move_xy(0, y + line_num) + term.clear_eol)

        rating_val_a = round(rating_a.get("rating", 1500))
        count_a = rating_a.get("comparison_count", 0)
        rating_val_b = round(rating_b.get("rating", 1500))
        count_b = rating_b.get("comparison_count", 0)

        # Format rating text with icon based on comparison count threshold
        threshold = 10
        if count_a >= threshold:
            icon_a = "⭐"
        else:
            icon_a = "⚠️"

        if count_b >= threshold:
            icon_b = "⭐"
        else:
            icon_b = "⚠️"

        rating_text_a = f"{icon_a} Rating: {rating_val_a} ({count_a})"
        rating_text_b = f"{icon_b} Rating: {rating_val_b} ({count_b})"

        # Apply highlighting
        if is_highlighted_a:
            rating_a_styled = term.bold_yellow(rating_text_a)
        else:
            rating_a_styled = term.yellow(rating_text_a)

        if is_highlighted_b:
            rating_b_styled = term.bold_yellow(rating_text_b)
        else:
            rating_b_styled = term.yellow(rating_text_b)

        sys.stdout.write(
            term.move_xy(2, y + line_num)
            + rating_a_styled
            + term.move_xy(center_col, y + line_num)
            + term.white("│")
            + term.move_xy(center_col + 2, y + line_num)
            + rating_b_styled
        )
        line_num += 1

    # Playing indicator
    if is_playing_a or is_playing_b:
        if line_num < max_height:
            # Clear the line first to remove any leftover placeholder text
            sys.stdout.write(term.move_xy(0, y + line_num) + term.clear_eol)

            playing_a_text = "▶ Playing..." if is_playing_a else ""
            playing_b_text = "▶ Playing..." if is_playing_b else ""

            # Apply highlighting
            if is_highlighted_a and is_playing_a:
                playing_a_styled = term.bold_green(playing_a_text)
            elif is_playing_a:
                playing_a_styled = term.green(playing_a_text)
            else:
                playing_a_styled = ""

            if is_highlighted_b and is_playing_b:
                playing_b_styled = term.bold_green(playing_b_text)
            elif is_playing_b:
                playing_b_styled = term.green(playing_b_text)
            else:
                playing_b_styled = ""

            sys.stdout.write(
                term.move_xy(2, y + line_num)
                + playing_a_styled
                + term.move_xy(center_col, y + line_num)
                + term.white("│")
                + term.move_xy(center_col + 2, y + line_num)
                + playing_b_styled
            )
            line_num += 1

    # Blank line separator
    if line_num < max_height:
        sys.stdout.write(term.move_xy(0, y + line_num) + term.clear_eol)
        line_num += 1

    return line_num


def render_session_progress(
    term: Terminal, comparison: ComparisonState, y: int, height: int
) -> int:
    """
    Render session progress and filter info.

    Args:
        term: Terminal instance
        comparison: Comparison state
        y: Starting Y position
        height: Available height

    Returns:
        Number of lines used
    """
    line_num = 0

    # Session progress
    if line_num < height:
        progress_text = f"   Session: {comparison.comparisons_done}/{comparison.target_comparisons} comparisons"
        sys.stdout.write(term.move_xy(0, y + line_num) + term.cyan(progress_text))
        line_num += 1

    # Filter info (if applicable)
    filter_parts = []
    if comparison.playlist_id:
        filter_parts.append(f"Playlist #{comparison.playlist_id}")
    if comparison.genre_filter:
        filter_parts.append(comparison.genre_filter)
    if comparison.year_filter:
        filter_parts.append(str(comparison.year_filter))

    if filter_parts and line_num < height:
        # Get track count from database (placeholder - would need actual query)
        # For now, just show filter info
        filter_text = f"   Filter: {' • '.join(filter_parts)}"
        sys.stdout.write(term.move_xy(0, y + line_num) + term.white(filter_text))
        line_num += 1

    # Blank line before footer
    if line_num < height:
        sys.stdout.write(term.move_xy(0, y + line_num) + term.clear_eol)
        line_num += 1

    return line_num


def _get_rating_info(track: dict[str, Any] | None) -> dict[str, Any]:
    """
    Extract rating information from track.

    Args:
        track: Track dictionary

    Returns:
        Dictionary with rating and comparison_count
    """
    if not track:
        return {"rating": 1500, "comparison_count": 0}

    return {
        "rating": track.get("rating", 1500),
        "comparison_count": track.get("comparison_count", 0),
    }


def _render_loading_skeleton(
    term: Terminal, comparison: ComparisonState, y: int, height: int
) -> None:
    """
    Render loading skeleton while tracks are being loaded in background.

    Args:
        term: Terminal instance
        comparison: Comparison state (in loading state)
        y: Starting Y position
        height: Available height
    """
    line_num = 0

    # Header
    if line_num < height:
        header_text = "   🎵 Track Comparison"
        sys.stdout.write(term.move_xy(0, y + line_num) + term.bold_cyan(header_text))
        line_num += 1

    # Separator
    if line_num < height:
        sys.stdout.write(term.move_xy(0, y + line_num) + term.white("   " + "─" * 60))
        line_num += 1

    # Loading message with spinner
    if line_num < height:
        # Build filter description
        filter_parts = []
        if comparison.source_filter and comparison.source_filter != "all":
            filter_parts.append(f"{comparison.source_filter}")
        if comparison.genre_filter:
            filter_parts.append(f"genre={comparison.genre_filter}")
        if comparison.year_filter:
            filter_parts.append(f"year={comparison.year_filter}")
        if comparison.playlist_id:
            filter_parts.append(f"playlist={comparison.playlist_id}")

        filter_desc = f" ({', '.join(filter_parts)})" if filter_parts else ""

        loading_text = f"   ⏳ Loading tracks{filter_desc}..."
        sys.stdout.write(term.move_xy(0, y + line_num) + term.yellow(loading_text))
        line_num += 1

    # Blank lines for spacing
    if line_num < height:
        sys.stdout.write(term.move_xy(0, y + line_num) + term.clear_eol)
        line_num += 1

    # Skeleton track placeholders
    if line_num < height:
        center_col = term.width // 2

        # Track headers
        sys.stdout.write(
            term.move_xy(2, y + line_num)
            + term.white("[←] Track A")
            + term.move_xy(center_col, y + line_num)
            + term.white("│")
            + term.move_xy(center_col + 2, y + line_num)
            + term.white("[→] Track B")
        )
        line_num += 1

    # Placeholder track info lines
    for _ in range(3):
        if line_num < height:
            placeholder_a = "   ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓"
            placeholder_b = "   ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓"

            sys.stdout.write(
                term.move_xy(2, y + line_num)
                + term.bright_black(placeholder_a)
                + term.move_xy(center_col, y + line_num)
                + term.white("│")
                + term.move_xy(center_col + 2, y + line_num)
                + term.bright_black(placeholder_b)
            )
            line_num += 1

    # Blank line
    if line_num < height:
        sys.stdout.write(term.move_xy(0, y + line_num) + term.clear_eol)
        line_num += 1

    # Session progress
    if line_num < height:
        progress_text = f"   Session: 0/{comparison.target_comparisons} comparisons"
        sys.stdout.write(term.move_xy(0, y + line_num) + term.cyan(progress_text))
        line_num += 1

    # Clear remaining lines
    while line_num < height - 1:
        sys.stdout.write(term.move_xy(0, y + line_num) + term.clear_eol)
        line_num += 1

    # Footer help text
    if line_num < height:
        footer = "   Please wait..."
        sys.stdout.write(term.move_xy(0, y + line_num) + term.bright_black(footer))
        line_num += 1
