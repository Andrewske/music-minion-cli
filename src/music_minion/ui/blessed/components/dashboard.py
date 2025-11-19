"""Dashboard rendering functions."""

from datetime import datetime
from typing import Optional
from blessed import Terminal
from music_minion.domain.playback.player import PlayerState
from ..state import UIState, TrackMetadata, TrackDBInfo


# Icon constants
ICONS = {
    "music": "♪",
    "note": "♫",
    "tag": "🏷️",
    "memo": "📝",
    "star": "⭐",
    "scroll": "📜",
    "heart": "💖",
}


def render_dashboard(term: Terminal, player_state: PlayerState, ui_state: UIState, y_start: int) -> tuple[int, dict]:
    """
    Render dashboard section.

    Args:
        term: blessed Terminal instance
        player_state: Player state from AppContext
        ui_state: UI state with cached display data
        y_start: Starting y position

    Returns:
        Tuple of (height_used, line_mapping) where line_mapping contains:
        - 'header_line': Line number for header with clock
        - 'progress_line': Line number for progress bar
        - 'bpm_line': Line number for BPM visualizer (if present)
    """
    lines = []
    line_mapping = {}
    metadata = ui_state.track_metadata
    db_info = ui_state.track_db_info

    # Header with clock and active library
    current_time = datetime.now().strftime("%H:%M:%S")

    # Get active library color
    library = ui_state.active_library
    if library == 'soundcloud':
        library_color = term.bold_cyan
    elif library == 'spotify':
        library_color = term.bold_green
    elif library == 'youtube':
        library_color = term.bold_red
    else:  # local or all
        library_color = term.bold_white

    # Calculate header length (plain text for alignment)
    header_text = f"{ICONS['music']} MUSIC MINION [{library}] {ICONS['music']}"
    header_len = len(header_text)
    time_len = len(f"[{current_time}]")
    spacer_width = max(term.width - header_len - time_len - 4, 2)

    # Build header with colors
    hour = datetime.now().hour
    if 6 <= hour < 12:
        time_color = term.bold_yellow
    elif 12 <= hour < 18:
        time_color = term.bold_blue
    elif 18 <= hour < 22:
        time_color = term.bold_yellow
    else:
        time_color = term.bold_magenta

    header = (
        term.bold_magenta(ICONS['music']) + " " +
        term.bold_cyan("MUSIC") + " " +
        term.bold_blue("MINION") + " " +
        library_color(f"[{library}]") + " " +
        term.bold_magenta(ICONS['music']) +
        " " * spacer_width +
        time_color(f"[{current_time}]")
    )
    line_mapping['header_line'] = len(lines)
    lines.append(header)

    # Colorful separator
    separator_chars = []
    colors = [term.cyan, term.blue, term.magenta, term.yellow]
    for i in range(term.width - 4):
        separator_chars.append(colors[i % 4]("━"))
    lines.append("".join(separator_chars))
    lines.append("")

    # Scan progress (takes priority over normal display)
    scan_progress = ui_state.scan_progress
    if scan_progress.is_scanning:
        scan_lines = format_scan_progress(scan_progress, term)
        lines.extend(scan_lines)
        lines.append("")
        lines.append("")
        # Skip normal track display
    # Track information
    elif player_state.current_track:
        if metadata:
            track_lines = format_track_display(metadata, term)
            lines.extend(track_lines)
        else:
            # Track is playing but no metadata yet (not in DB or lookup failed)
            import os
            filename = os.path.basename(player_state.current_track)
            lines.append(term.bold_white(f"{ICONS['note']} {filename}"))
            lines.append(term.white("  Loading metadata..."))
    else:
        lines.append(term.white(f"{ICONS['note']} No track playing"))
        lines.append(term.white("  Waiting for music..."))

    lines.append("")

    # Progress bar
    if player_state.is_playing:
        progress = create_progress_bar(player_state.current_position, player_state.duration, term)
        line_mapping['progress_line'] = len(lines)
        lines.append(progress)

        # BPM visualizer
        if metadata and metadata.bpm:
            bpm_line = format_bpm_line(metadata.bpm, term)
            line_mapping['bpm_line'] = len(lines)
            lines.append(bpm_line)
    else:
        lines.append(term.white("─" * 40))
        lines.append(term.bold_yellow("⏸ Paused"))

    lines.append("")

    # Tags and notes
    if db_info:
        tag_lines = format_tags_and_notes(db_info.tags, db_info.notes, term)
        for line, style in tag_lines:
            if style == 'tag':
                lines.append(term.bold_blue(line))
            elif style == 'note':
                lines.append(term.bold_green(line))
            else:
                lines.append(term.blue(line))

        # Rating
        if db_info.rating is not None or db_info.last_played:
            rating_line = format_rating(db_info.rating, db_info.last_played, db_info.play_count)
            if db_info.rating and db_info.rating >= 80:
                rating_style = term.bold_red
            elif db_info.rating and db_info.rating >= 60:
                rating_style = term.bold_yellow
            elif db_info.rating and db_info.rating <= 20:
                rating_style = term.white
            else:
                rating_style = term.white
            lines.append(rating_style(rating_line))

    lines.append("")

    # Feedback
    from ..state import should_show_feedback
    if should_show_feedback(ui_state):
        feedback = ui_state.feedback_message
        if feedback:
            if "loved" in feedback.lower() or "❤️" in feedback:
                style = term.bold_red
            elif "liked" in feedback.lower() or "👍" in feedback:
                style = term.bold_yellow
            elif "archived" in feedback.lower():
                style = term.bold_red
            elif "skipped" in feedback.lower():
                style = term.bold_cyan
            elif "note" in feedback.lower():
                style = term.bold_green
            else:
                style = term.bold_white
            lines.append(style(feedback))

    # Active playlist info
    playlist_info = ui_state.playlist_info
    if playlist_info.name:
        playlist_line = f"📋 Playlist: {playlist_info.name}"
        lines.append(term.bold_cyan(playlist_line))

        if playlist_info.current_position is not None and not ui_state.shuffle_enabled:
            position_line = f"   Position: {playlist_info.current_position + 1}/{playlist_info.track_count}"
            lines.append(term.cyan(position_line))

    # Shuffle mode
    shuffle_icon = "🔀" if ui_state.shuffle_enabled else "🔁"
    shuffle_text = "Shuffle ON" if ui_state.shuffle_enabled else "Sequential"
    shuffle_line = f"{shuffle_icon} {shuffle_text}"
    shuffle_style = term.bold_yellow if ui_state.shuffle_enabled else term.bold_green
    lines.append(shuffle_style(shuffle_line))

    # Dashboard bottom separator
    lines.append("")
    separator_chars = []
    colors = [term.cyan, term.blue, term.magenta, term.yellow]
    for i in range(term.width - 4):
        separator_chars.append(colors[i % 4]("━"))
    lines.append("".join(separator_chars))

    # Render all lines
    for i, line in enumerate(lines):
        print(term.move_xy(0, y_start + i) + line)

    return len(lines), line_mapping


def format_artists(artist_string: str) -> str:
    """
    Format semicolon-separated artists for display.

    Examples:
        "Artist1" -> "Artist1"
        "Artist1; Artist2" -> "Artist1 & Artist2"
        "Artist1; Artist2; Artist3" -> "Artist1, Artist2 & Artist3"

    Args:
        artist_string: Semicolon-separated artist names

    Returns:
        Formatted artist string
    """
    if not artist_string:
        return "Unknown"

    # Split on semicolons and strip whitespace
    artists = [a.strip() for a in artist_string.split(';') if a.strip()]

    if not artists:
        return "Unknown"
    elif len(artists) == 1:
        return artists[0]
    elif len(artists) == 2:
        return f"{artists[0]} & {artists[1]}"
    else:
        # Three or more: "A, B, C & D"
        return ", ".join(artists[:-1]) + f" & {artists[-1]}"


def format_track_display(metadata: TrackMetadata, term: Terminal) -> list[str]:
    """Format track information for display."""
    lines = []
    lines.append(term.bold_white(f"{ICONS['note']} {metadata.title}"))

    # Format main artists
    formatted_artists = format_artists(metadata.artist)
    lines.append(term.bold_blue(f"  by {formatted_artists}"))

    # Show remix artists if present
    if metadata.remix_artist:
        formatted_remix = format_artists(metadata.remix_artist)
        lines.append(term.blue(f"  remix by {formatted_remix}"))

    details = []
    if metadata.album:
        details.append(metadata.album)
    if metadata.year:
        details.append(f"({metadata.year})")
    if metadata.genre:
        details.append(f"| {metadata.genre}")
    if metadata.bpm:
        details.append(f"| {metadata.bpm} BPM")
    if metadata.key:
        details.append(f"| {metadata.key}")

    if details:
        lines.append(term.blue("  " + " ".join(details)))

    return lines


def create_progress_bar(position: float, duration: float, term: Terminal) -> str:
    """Create a colored progress bar."""
    if duration <= 0:
        return term.white("─" * 40)

    percentage = min(position / duration, 1.0)
    bar_width = 40
    filled = int(bar_width * percentage)

    progress_parts = []
    for i in range(filled):
        char_percentage = (i + 1) / bar_width
        if char_percentage < 0.33:
            progress_parts.append(term.green("█"))
        elif char_percentage < 0.66:
            progress_parts.append(term.yellow("█"))
        else:
            progress_parts.append(term.red("█"))

    progress_parts.append(term.white("░" * (bar_width - filled)))

    # Add time displays
    current = format_time(position)
    total = format_time(duration)
    progress_parts.append(term.white(f" {current} "))
    progress_parts.append(term.cyan("━━━━"))
    progress_parts.append(term.white(f" {total}"))

    return "".join(progress_parts)


def format_bpm_line(bpm: int, term: Terminal) -> str:
    """Format BPM line with color based on tempo."""
    if bpm < 90:
        color = term.blue
    elif bpm < 120:
        color = term.cyan
    elif bpm < 140:
        color = term.yellow
    else:
        color = term.red

    return color(f"{ICONS['music']} {bpm} BPM {ICONS['music']}")


def format_tags_and_notes(tags: list[str], notes: str, term: Terminal) -> list[tuple[str, str]]:
    """Format tags and notes for display. Returns list of (text, style_key) tuples."""
    lines = []

    if tags:
        tag_line = f"{ICONS['tag']}  " + " • ".join(tags[:5])
        lines.append((tag_line, 'tag'))

    if notes:
        if len(notes) > 60:
            notes = notes[:57] + "..."
        lines.append((f"{ICONS['memo']} \"{notes}\"", 'note'))

    return lines


def format_rating(rating: Optional[int], last_played: Optional[str], play_count: int) -> str:
    """Format rating and play statistics."""
    stars = ""
    if rating is not None:
        filled = min(max(rating // 20, 0), 5)
        stars = "★" * filled + "☆" * (5 - filled)
    else:
        stars = "☆☆☆☆☆"

    parts = [f"{ICONS['star']} {stars}"]

    if last_played:
        parts.append(f"| Last: {last_played}")

    if play_count > 0:
        parts.append(f"| Total plays: {play_count}")

    return " ".join(parts)


def format_time(seconds: float) -> str:
    """Format seconds to MM:SS display."""
    if seconds < 0 or seconds > 86400:
        return "--:--"
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes}:{secs:02d}"


def format_scan_progress(scan_progress, term: Terminal) -> list[str]:
    """Format library scan progress display.

    Args:
        scan_progress: ScanProgress object with scan state
        term: blessed Terminal instance

    Returns:
        List of formatted lines for display
    """
    from ..state import ScanProgress

    lines = []

    # Title
    lines.append(term.bold_cyan("🔍 Library Scan in Progress"))
    lines.append("")

    # Phase indicator
    if scan_progress.phase == 'counting':
        lines.append(term.yellow("  📊 Counting files..."))
    elif scan_progress.phase == 'scanning':
        lines.append(term.yellow("  🎵 Scanning music files..."))
    elif scan_progress.phase == 'database':
        lines.append(term.yellow("  💾 Updating database..."))

    # Progress bar
    if scan_progress.total_files > 0:
        percentage = min(scan_progress.files_scanned / scan_progress.total_files, 1.0)
        bar_width = 40
        filled = int(bar_width * percentage)

        # Create progress bar
        progress_parts = []
        for i in range(filled):
            progress_parts.append(term.cyan("█"))
        progress_parts.append(term.white("░" * (bar_width - filled)))

        # Add counts
        progress_parts.append(term.white(f" {scan_progress.files_scanned}/{scan_progress.total_files}"))
        progress_parts.append(term.yellow(f" ({percentage * 100:.1f}%)"))

        lines.append("  " + "".join(progress_parts))

    # Current file (truncate if too long)
    if scan_progress.current_file:
        current_file = scan_progress.current_file
        max_width = term.width - 10
        if len(current_file) > max_width:
            current_file = "..." + current_file[-(max_width - 3):]
        lines.append(term.white(f"  {current_file}"))

    return lines


def render_dashboard_partial(term: Terminal, player_state: PlayerState, ui_state: UIState,
                           y_start: int, line_mapping: dict) -> None:
    """
    Partially update dashboard - only time-sensitive elements.

    This updates only the clock and progress bar without clearing the screen,
    eliminating flashing when only playback position changes.

    Args:
        term: blessed Terminal instance
        player_state: Player state from AppContext
        ui_state: UI state with cached display data
        y_start: Starting y position of dashboard
        line_mapping: Dictionary with line offsets from render_dashboard
    """
    metadata = ui_state.track_metadata

    # Update clock in header
    if 'header_line' in line_mapping:
        current_time = datetime.now().strftime("%H:%M:%S")

        # Get active library color (same as full render)
        library = ui_state.active_library
        if library == 'soundcloud':
            library_color = term.bold_cyan
        elif library == 'spotify':
            library_color = term.bold_green
        elif library == 'youtube':
            library_color = term.bold_red
        else:  # local or all
            library_color = term.bold_white

        # Calculate header length (plain text for alignment)
        header_text = f"{ICONS['music']} MUSIC MINION [{library}] {ICONS['music']}"
        header_len = len(header_text)
        time_len = len(f"[{current_time}]")
        spacer_width = max(term.width - header_len - time_len - 4, 2)

        # Build header with colors (same as full render)
        hour = datetime.now().hour
        if 6 <= hour < 12:
            time_color = term.bold_yellow
        elif 12 <= hour < 18:
            time_color = term.bold_blue
        elif 18 <= hour < 22:
            time_color = term.bold_yellow
        else:
            time_color = term.bold_magenta

        header = (
            term.bold_magenta(ICONS['music']) + " " +
            term.bold_cyan("MUSIC") + " " +
            term.bold_blue("MINION") + " " +
            library_color(f"[{library}]") + " " +
            term.bold_magenta(ICONS['music']) +
            " " * spacer_width +
            time_color(f"[{current_time}]")
        )

        # Update clock line - clear and rewrite
        header_y = y_start + line_mapping['header_line']
        print(term.move_xy(0, header_y) + term.clear_eol + header, end='')

    # Update progress bar if playing
    if player_state.is_playing and player_state.current_track and 'progress_line' in line_mapping:
        progress = create_progress_bar(player_state.current_position, player_state.duration, term)
        progress_y = y_start + line_mapping['progress_line']
        print(term.move_xy(0, progress_y) + term.clear_eol + progress, end='')

        # Update BPM line if metadata available
        if metadata and metadata.bpm and 'bpm_line' in line_mapping:
            bpm_line = format_bpm_line(metadata.bpm, term)
            bpm_y = y_start + line_mapping['bpm_line']
            print(term.move_xy(0, bpm_y) + term.clear_eol + bpm_line, end='')
