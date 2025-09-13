"""
Terminal UI module for Music Minion CLI
Retro hi-fi aesthetic with Rich library for rendering
"""

import sys
import time
from datetime import datetime
from typing import Optional, Dict, Any, List

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.text import Text
from rich.align import Align

console = Console()

# BPM visualizer patterns
BPM_PATTERNS = [
    "[●····]",
    "[·●···]", 
    "[··●··]",
    "[···●·]",
    "[····●]",
    "[···●·]",
    "[··●··]",
    "[·●···]",
]

# Config reference for UI settings
ui_config = None

# Emoji detection and fallback
def supports_emoji() -> bool:
    """Check if terminal supports emoji."""
    # Use config setting if available, otherwise use platform heuristic
    if ui_config and hasattr(ui_config, 'use_emoji'):
        return ui_config.use_emoji
    return sys.platform != "win32"

# Icons with ASCII fallbacks
ICONS = {
    "music": "♪" if supports_emoji() else "*",
    "note": "♫" if supports_emoji() else "~",
    "tag": "🏷️" if supports_emoji() else "#",
    "memo": "📝" if supports_emoji() else ">",
    "star": "⭐" if supports_emoji() else "*",
    "scroll": "📜" if supports_emoji() else "[]",
    "heart": "💖" if supports_emoji() else "<3",
}

# Track state for animations and feedback
ui_state = {
    "bpm_frame": 0,
    "last_beat_time": time.time(),
    "feedback_message": None,
    "feedback_time": None,
    "previous_track": None,
    "previous_rating": None,
    "previous_time": None,
}


def format_time(seconds: float) -> str:
    """Format seconds to MM:SS display."""
    if seconds < 0 or seconds > 86400:  # More than 24 hours
        return "--:--"
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes}:{secs:02d}"


def set_ui_config(config) -> None:
    """Set the UI configuration."""
    global ui_config, ICONS
    ui_config = config
    # Update icons based on config
    ICONS = {
        "music": "♪" if supports_emoji() else "*",
        "note": "♫" if supports_emoji() else "~",
        "tag": "🏷️" if supports_emoji() else "#",
        "memo": "📝" if supports_emoji() else ">",
        "star": "⭐" if supports_emoji() else "*",
        "scroll": "📜" if supports_emoji() else "[]",
        "heart": "💖" if supports_emoji() else "<3",
    }


def get_bpm_visualizer(bpm: int = 120) -> str:
    """Get current frame of BPM visualizer based on tempo."""
    global ui_state, ui_config
    
    # Check if visualizer is enabled
    if ui_config and hasattr(ui_config, 'bpm_visualizer') and not ui_config.bpm_visualizer:
        return f"{bpm} BPM"
    
    # Calculate time per beat
    seconds_per_beat = 60.0 / bpm
    
    # Check if we should advance frame
    current_time = time.time()
    if current_time - ui_state["last_beat_time"] >= seconds_per_beat:
        ui_state["bpm_frame"] = (ui_state["bpm_frame"] + 1) % len(BPM_PATTERNS)
        ui_state["last_beat_time"] = current_time
    
    return BPM_PATTERNS[ui_state["bpm_frame"]]


def create_progress_bar(position: float, duration: float) -> str:
    """Create a custom progress bar with blocks."""
    if duration <= 0:
        return "─" * 40
    
    percentage = min(position / duration, 1.0)
    bar_length = 40
    filled = int(bar_length * percentage)
    
    # Use block characters for filled/empty
    bar = "█" * filled + "░" * (bar_length - filled)
    
    # Add time displays
    current = format_time(position)
    total = format_time(duration)
    
    return f"{bar} {current} ──── {total}"


def create_progress_bar_responsive(position: float, duration: float, bar_width: int = 40) -> str:
    """Create a responsive progress bar that adapts to console width."""
    if duration <= 0:
        return "─" * bar_width
    
    percentage = min(position / duration, 1.0)
    
    # Reserve space for time displays (MM:SS ──── MM:SS = about 14 chars)
    time_space = 14
    actual_bar_width = max(bar_width - time_space, 10)
    
    filled = int(actual_bar_width * percentage)
    
    # Use block characters for filled/empty
    bar = "█" * filled + "░" * (actual_bar_width - filled)
    
    # Add time displays
    current = format_time(position)
    total = format_time(duration)
    
    return f"{bar} {current} ──── {total}"


def format_track_display(track_info: Dict[str, Any]) -> List[str]:
    """Format track information for display."""
    lines = []
    
    if not track_info or not track_info.get("title"):
        lines.append(f"{ICONS['note']} No track playing")
        lines.append("  Waiting for music...")
        return lines
    
    # Artist - Title
    artist = track_info.get("artist", "Unknown Artist")
    title = track_info.get("title", "Unknown Title")
    lines.append(f"{ICONS['note']} {artist} - {title}")
    
    # Album, year, genre, BPM, key
    details = []
    if album := track_info.get("album"):
        details.append(album)
    if year := track_info.get("year"):
        details.append(f"({year})")
    if genre := track_info.get("genre"):
        details.append(f"| {genre}")
    if bpm := track_info.get("bpm"):
        details.append(f"| {bpm} BPM")
    if key := track_info.get("key"):
        details.append(f"| {key}")
    
    if details:
        lines.append("  " + " ".join(details))
    
    return lines


def format_tags_and_notes(tags: List[str], notes: str) -> List[str]:
    """Format tags and notes for display."""
    lines = []
    
    if tags:
        tag_line = f"{ICONS['tag']}  " + " • ".join(tags[:5])  # Limit to 5 tags
        lines.append(tag_line)
    
    if notes:
        # Truncate long notes
        if len(notes) > 60:
            notes = notes[:57] + "..."
        lines.append(f"{ICONS['memo']} \"{notes}\"")
    
    return lines


def format_rating_display(rating: Optional[int], last_played: Optional[str], 
                         play_count: int = 0) -> str:
    """Format rating and play statistics."""
    # Convert numeric rating to stars
    stars = ""
    if rating is not None:
        filled = min(max(rating // 20, 0), 5)  # 0-100 -> 0-5 stars
        stars = "★" * filled + "☆" * (5 - filled)
    else:
        stars = "☆☆☆☆☆"
    
    parts = [f"{ICONS['star']} {stars}"]
    
    if last_played:
        parts.append(f"| Last: {last_played}")
    
    if play_count > 0:
        parts.append(f"| Total plays: {play_count}")
    
    return " ".join(parts)


def format_previous_track(track_info: Optional[Dict], rating: Optional[str]) -> str:
    """Format previous track display."""
    if not track_info:
        return ""
    
    artist = track_info.get("artist", "Unknown")
    title = track_info.get("title", "Unknown")
    
    rating_str = ""
    if rating == "love":
        rating_str = "★★★★"
    elif rating == "like":
        rating_str = "★★★"
    elif rating == "skip":
        rating_str = "skipped"
    elif rating == "archive":
        rating_str = "archived"
    
    time_ago = track_info.get("time_ago", "just now")
    
    return f"{ICONS['scroll']} Previous: {artist} - {title} ({rating_str} • {time_ago})"


def set_feedback(message: str, icon: str = None) -> None:
    """Set a feedback message to display."""
    global ui_state
    if icon:
        ui_state["feedback_message"] = f"{icon} {message}"
    else:
        ui_state["feedback_message"] = message
    ui_state["feedback_time"] = time.time()


def get_feedback() -> Optional[str]:
    """Get current feedback message if it should still be shown."""
    global ui_state
    
    if not ui_state["feedback_message"]:
        return None
    
    # Show feedback for 4 seconds
    if time.time() - ui_state["feedback_time"] > 4:
        ui_state["feedback_message"] = None
        return None
    
    return ui_state["feedback_message"]


def store_previous_track(track_info: Dict[str, Any], rating: str) -> None:
    """Store information about the previous track."""
    global ui_state
    ui_state["previous_track"] = track_info.copy()
    ui_state["previous_rating"] = rating
    ui_state["previous_time"] = time.time()


def render_dashboard(player_state: Any, track_metadata: Optional[Dict] = None,
                    db_info: Optional[Dict] = None, console_width: int = 80) -> Panel:
    """
    Render the complete dashboard panel.
    
    Args:
        player_state: Current player state object
        track_metadata: Additional metadata from database/files
        db_info: Database information (tags, notes, ratings, etc.)
        console_width: Width of console for responsive layout
    """
    # Build display lines
    lines = []
    
    # Header with clock - adjust spacing based on console width
    current_time = datetime.now().strftime("%H:%M:%S")
    header = Text()
    header.append(f"{ICONS['music']} MUSIC MINION", style="bold cyan")
    
    # Calculate spacer dynamically based on console width
    header_text = f"{ICONS['music']} MUSIC MINION"
    time_text = f"[{current_time}]"
    spacer_width = max(console_width - len(header_text) - len(time_text) - 4, 2)
    header.append(" " * spacer_width)
    header.append(time_text, style="dim")
    lines.append(header)
    
    # Separator adjusted to console width
    separator_width = min(console_width - 4, 60)
    lines.append(Text("─" * separator_width, style="dim"))
    
    # Empty line for spacing
    lines.append("")
    
    # Track information
    track_info = {}
    if player_state and player_state.current_track:
        # Combine player state and metadata
        track_info["file"] = player_state.current_track
        if track_metadata:
            track_info.update(track_metadata)
    
    track_lines = format_track_display(track_info)
    for line in track_lines:
        # Truncate long lines to fit console width
        truncated_line = line[:console_width - 6] + "..." if len(line) > console_width - 3 else line
        lines.append(Text(truncated_line, style="white"))
    
    lines.append("")  # Spacing
    
    # Progress bar - adjust width to console
    if player_state and player_state.is_playing:
        # Calculate progress bar width based on console
        bar_width = min(max(console_width - 20, 20), 60)
        progress = create_progress_bar_responsive(
            player_state.current_position,
            player_state.duration,
            bar_width
        )
        lines.append(Text(progress, style="cyan"))
        
        # BPM visualizer
        bpm = track_metadata.get("bpm", 120) if track_metadata else 120
        visualizer = get_bpm_visualizer(bpm)
        bpm_line = f"{ICONS['music']} {visualizer} {bpm} BPM {ICONS['music']}"
        lines.append(Text(bpm_line[:console_width - 6], style="magenta"))
    else:
        bar_width = min(max(console_width - 10, 20), 40)
        lines.append(Text("─" * bar_width, style="dim"))
        lines.append(Text("⏸ Paused", style="yellow"))
    
    lines.append("")  # Spacing
    
    # Tags and notes from database
    if db_info:
        tags = db_info.get("tags", [])
        notes = db_info.get("notes", "")
        tag_lines = format_tags_and_notes(tags, notes)
        for line in tag_lines:
            # Truncate tag lines to fit
            truncated_line = line[:console_width - 6] + "..." if len(line) > console_width - 3 else line
            lines.append(Text(truncated_line, style="blue"))
        
        # Rating and statistics
        rating = db_info.get("rating")
        last_played = db_info.get("last_played")
        play_count = db_info.get("play_count", 0)
        rating_line = format_rating_display(rating, last_played, play_count)
        if rating_line:
            truncated_rating = rating_line[:console_width - 6] + "..." if len(rating_line) > console_width - 3 else rating_line
            lines.append(Text(truncated_rating, style="yellow"))
    
    lines.append("")  # Spacing
    
    # Feedback message or previous track
    if feedback := get_feedback():
        truncated_feedback = feedback[:console_width - 6] + "..." if len(feedback) > console_width - 3 else feedback
        lines.append(Text(truncated_feedback, style="bold green"))
    elif ui_state["previous_track"]:
        # Calculate time ago
        if ui_state["previous_time"]:
            seconds_ago = int(time.time() - ui_state["previous_time"])
            if seconds_ago < 60:
                time_ago = f"{seconds_ago}s ago"
            else:
                time_ago = f"{seconds_ago // 60} min ago"
            ui_state["previous_track"]["time_ago"] = time_ago
        
        prev_line = format_previous_track(
            ui_state["previous_track"],
            ui_state["previous_rating"]
        )
        truncated_prev = prev_line[:console_width - 6] + "..." if len(prev_line) > console_width - 3 else prev_line
        lines.append(Text(truncated_prev, style="dim"))
    
    # Create panel with all lines
    content = "\n".join(str(line) for line in lines)
    
    # Calculate panel width to fit console
    panel_width = min(console_width, 80)
    
    panel = Panel(
        content,
        border_style="bright_white",
        padding=(1, 2),
        width=panel_width,
        height=None,  # Let height be dynamic based on content
    )
    
    return panel


def clear_session() -> None:
    """Clear session-specific UI state."""
    global ui_state
    ui_state["previous_track"] = None
    ui_state["previous_rating"] = None
    ui_state["previous_time"] = None
    ui_state["feedback_message"] = None
    ui_state["feedback_time"] = None


# Action feedback animations
def flash_love() -> None:
    """Show love animation feedback."""
    set_feedback("Track loved!", ICONS["heart"])


def flash_skip() -> None:
    """Show skip animation feedback."""  
    set_feedback("Skipped to next track", "⏭")


def flash_archive() -> None:
    """Show archive animation feedback."""
    set_feedback("Track archived - won't play again", "🗄")


def flash_like() -> None:
    """Show like animation feedback."""
    set_feedback("Track liked!", "👍")


def flash_note_added() -> None:
    """Show note added feedback."""
    set_feedback("Note added to track", ICONS["memo"])