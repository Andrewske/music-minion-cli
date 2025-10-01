"""Dashboard rendering functions."""

from datetime import datetime
from typing import Optional
from blessed import Terminal
from ..state import UIState, TrackMetadata, TrackDBInfo, PlayerState


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


def render_dashboard(term: Terminal, state: UIState, y_start: int) -> int:
    """
    Render dashboard section.

    Args:
        term: blessed Terminal instance
        state: Current UI state
        y_start: Starting y position

    Returns:
        Height used by dashboard
    """
    lines = []
    player = state.player
    metadata = state.track_metadata
    db_info = state.track_db_info

    # Header with clock
    current_time = datetime.now().strftime("%H:%M:%S")
    header_text = f"{ICONS['music']} MUSIC MINION {ICONS['music']}"

    # Calculate spacer for time alignment
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
        term.bold_magenta(ICONS['music']) +
        " " * spacer_width +
        time_color(f"[{current_time}]")
    )
    lines.append(header)

    # Colorful separator
    separator_chars = []
    colors = [term.cyan, term.blue, term.magenta, term.yellow]
    for i in range(term.width - 4):
        separator_chars.append(colors[i % 4]("━"))
    lines.append("".join(separator_chars))
    lines.append("")

    # Track information
    if player.current_track and metadata:
        track_lines = format_track_display(metadata, term)
        lines.extend(track_lines)
    else:
        lines.append(term.white(f"{ICONS['note']} No track playing"))
        lines.append(term.white("  Waiting for music..."))

    lines.append("")

    # Progress bar
    if player.is_playing:
        progress = create_progress_bar(player.current_position, player.duration, term)
        lines.append(progress)

        # BPM visualizer
        if metadata and metadata.bpm:
            bpm_line = format_bpm_line(metadata.bpm, term)
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
    if should_show_feedback(state):
        feedback = state.feedback_message
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
    playlist_info = state.playlist_info
    if playlist_info.name:
        playlist_line = f"📋 Playlist: {playlist_info.name}"
        lines.append(term.bold_cyan(playlist_line))

        if playlist_info.current_position is not None and not state.shuffle_enabled:
            position_line = f"   Position: {playlist_info.current_position + 1}/{playlist_info.track_count}"
            lines.append(term.cyan(position_line))

    # Shuffle mode
    shuffle_icon = "🔀" if state.shuffle_enabled else "🔁"
    shuffle_text = "Shuffle ON" if state.shuffle_enabled else "Sequential"
    shuffle_line = f"{shuffle_icon} {shuffle_text}"
    shuffle_style = term.bold_yellow if state.shuffle_enabled else term.bold_green
    lines.append(shuffle_style(shuffle_line))

    # Render all lines
    for i, line in enumerate(lines):
        print(term.move_xy(0, y_start + i) + line)

    return len(lines)


def format_track_display(metadata: TrackMetadata, term: Terminal) -> list[str]:
    """Format track information for display."""
    lines = []
    lines.append(term.bold_white(f"{ICONS['note']} {metadata.title}"))
    lines.append(term.bold_blue(f"  by {metadata.artist}"))

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
