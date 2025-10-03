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

from music_minion.domain import playlists
from music_minion.domain import playback

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


def create_progress_bar_responsive(position: float, duration: float, bar_width: int = 40) -> Text:
    """Create a responsive progress bar with color gradients."""
    if duration <= 0:
        return Text("─" * bar_width, style="dim")
    
    percentage = min(position / duration, 1.0)
    
    # Reserve space for time displays (MM:SS ──── MM:SS = about 14 chars)
    time_space = 14
    actual_bar_width = max(bar_width - time_space, 10)
    
    filled = int(actual_bar_width * percentage)
    
    # Create colored progress bar
    progress_text = Text()
    
    # Filled portion with gradient
    for i in range(filled):
        char_percentage = (i + 1) / actual_bar_width
        if char_percentage < 0.33:
            progress_text.append("█", style="green")
        elif char_percentage < 0.66:
            progress_text.append("█", style="yellow")
        else:
            progress_text.append("█", style="red")
    
    # Empty portion
    progress_text.append("░" * (actual_bar_width - filled), style="dim")
    
    # Add time displays
    current = format_time(position)
    total = format_time(duration)
    
    progress_text.append(f" {current} ", style="white")
    progress_text.append("━━━━", style="cyan")
    progress_text.append(f" {total}", style="white")
    
    return progress_text


def parse_artists(artist_string: str) -> List[str]:
    """Parse multiple artists from a single artist string."""
    if not artist_string:
        return ["Unknown Artist"]
    
    # Common separators for multiple artists
    separators = [
        ' feat. ', ' ft. ', ' featuring ', ' Feat. ', ' Ft. ', ' Featuring ',
        ' & ', ' and ', ' And ', ' x ', ' X ', ' vs. ', ' vs ', ' Vs. ', ' VS ',
        ', ', ' with ', ' With '
    ]
    
    # Start with the original string
    artists = [artist_string]
    
    # Split by each separator
    for separator in separators:
        new_artists = []
        for artist in artists:
            if separator in artist:
                parts = artist.split(separator)
                new_artists.extend(parts)
            else:
                new_artists.append(artist)
        artists = new_artists
    
    # Clean up each artist name
    cleaned = []
    for artist in artists:
        artist = artist.strip()
        # Remove common suffixes/prefixes that might remain
        artist = artist.strip('(),[]')
        if artist and artist not in cleaned:  # Avoid duplicates
            cleaned.append(artist)
    
    return cleaned if cleaned else ["Unknown Artist"]


def format_track_display(track_info: Dict[str, Any]) -> List[str]:
    """Format track information for display."""
    lines = []
    
    if not track_info or not track_info.get("title"):
        lines.append(f"{ICONS['note']} No track playing")
        lines.append("  Waiting for music...")
        return lines
    
    # Title on its own line
    title = track_info.get("title", "Unknown Title")
    lines.append(f"{ICONS['note']} {title}")
    
    # Artists on separate line(s)
    artist_string = track_info.get("artist", "Unknown Artist")
    artists = parse_artists(artist_string)
    
    if len(artists) == 1:
        lines.append(f"  by {artists[0]}")
    else:
        # Multiple artists - show them nicely formatted
        lines.append(f"  by {artists[0]}")
        for artist in artists[1:]:
            lines.append(f"     {artist}")
    
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
    
    artist_string = track_info.get("artist", "Unknown")
    title = track_info.get("title", "Unknown")
    
    # For previous track, show all artists inline with separators
    artists = parse_artists(artist_string)
    artist_display = " & ".join(artists) if len(artists) > 1 else artists[0]
    
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
    
    return f"{ICONS['scroll']} Previous: {artist_display} - {title} ({rating_str} • {time_ago})"


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
    
    # Header with clock - colorful and dynamic
    current_time = datetime.now().strftime("%H:%M:%S")
    header = Text()
    
    # Colorful title with gradient effect
    header.append(f"{ICONS['music']} ", style="bold magenta")
    header.append("MUSIC", style="bold cyan")
    header.append(" ", style="white")
    header.append("MINION", style="bold blue")
    header.append(f" {ICONS['music']}", style="bold magenta")
    
    # Calculate spacer dynamically based on console width
    header_text = f"{ICONS['music']} MUSIC MINION {ICONS['music']}"
    time_text = f"[{current_time}]"
    spacer_width = max(console_width - len(header_text) - len(time_text) - 8, 2)
    header.append(" " * spacer_width)
    
    # Time with color based on time of day
    hour = datetime.now().hour
    if 6 <= hour < 12:
        time_style = "bold yellow"  # Morning
    elif 12 <= hour < 18:
        time_style = "bold blue"    # Afternoon  
    elif 18 <= hour < 22:
        time_style = "bold orange3"  # Evening
    else:
        time_style = "bold purple"  # Night
    
    header.append(f"[{current_time}]", style=time_style)
    lines.append(header)
    
    # Colorful separator adjusted to console width  
    separator_width = console_width - 8  # Account for panel padding
    # Create a gradient-like separator
    separator = Text()
    for i in range(separator_width):
        if i % 4 == 0:
            separator.append("━", style="cyan")
        elif i % 4 == 1:
            separator.append("━", style="blue")
        elif i % 4 == 2:
            separator.append("━", style="magenta")
        else:
            separator.append("━", style="purple")
    lines.append(separator)
    
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
    for i, line in enumerate(track_lines):
        # Truncate long lines to fit console width
        truncated_line = line[:console_width - 6] + "..." if len(line) > console_width - 3 else line
        
        # Color code different track info lines
        if i == 0:  # Artist - Title line
            lines.append(Text(truncated_line, style="bold white"))
        else:  # Album/details line
            lines.append(Text(truncated_line, style="bright_blue"))
    
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
        lines.append(progress)
        
        # BPM visualizer with pulsing colors
        bpm = track_metadata.get("bpm", 120) if track_metadata else 120
        visualizer = get_bpm_visualizer(bpm)
        
        # Color BPM based on tempo
        if bpm < 90:
            bpm_color = "blue"      # Slow/chill
        elif bpm < 120:
            bpm_color = "cyan"      # Medium
        elif bpm < 140:
            bpm_color = "yellow"    # Upbeat
        else:
            bpm_color = "red"       # Fast/energetic
            
        bpm_line = f"{ICONS['music']} {visualizer} {bpm} BPM {ICONS['music']}"
        lines.append(Text(bpm_line[:console_width - 6], style=f"bold {bpm_color}"))
    else:
        bar_width = min(max(console_width - 10, 20), 40)
        lines.append(Text("─" * bar_width, style="dim"))
        lines.append(Text("⏸ Paused", style="bold yellow on red"))
    
    lines.append("")  # Spacing
    
    # Tags and notes from database
    if db_info:
        tags = db_info.get("tags", [])
        notes = db_info.get("notes", "")
        tag_lines = format_tags_and_notes(tags, notes)
        for line in tag_lines:
            # Truncate tag lines to fit
            truncated_line = line[:console_width - 6] + "..." if len(line) > console_width - 3 else line
            
            # Color tags and notes differently
            if line.startswith(ICONS.get('tag', '#')):
                lines.append(Text(truncated_line, style="bold bright_blue"))
            elif line.startswith(ICONS.get('memo', '>')):
                lines.append(Text(truncated_line, style="italic bright_green"))
            else:
                lines.append(Text(truncated_line, style="blue"))
        
        # Rating and statistics with color coding
        rating = db_info.get("rating")
        last_played = db_info.get("last_played")
        play_count = db_info.get("play_count", 0)
        rating_line = format_rating_display(rating, last_played, play_count)
        if rating_line:
            truncated_rating = rating_line[:console_width - 6] + "..." if len(rating_line) > console_width - 3 else rating_line
            
            # Color rating based on score
            if rating and rating >= 80:
                rating_style = "bold bright_red"      # Love
            elif rating and rating >= 60:
                rating_style = "bold bright_yellow"   # Like
            elif rating and rating <= 20:
                rating_style = "dim"                  # Archive/skip
            else:
                rating_style = "white"                # Default
                
            lines.append(Text(truncated_rating, style=rating_style))
    
    lines.append("")  # Spacing
    
    # Feedback message or previous track
    if feedback := get_feedback():
        truncated_feedback = feedback[:console_width - 6] + "..." if len(feedback) > console_width - 3 else feedback
        
        # Color feedback based on content
        if "loved" in feedback.lower() or "❤️" in feedback:
            feedback_style = "bold bright_red on black"
        elif "liked" in feedback.lower() or "👍" in feedback:
            feedback_style = "bold bright_yellow on black"
        elif "archived" in feedback.lower():
            feedback_style = "bold bright_black on red"
        elif "skipped" in feedback.lower():
            feedback_style = "bold cyan on black"
        elif "note" in feedback.lower():
            feedback_style = "bold bright_green on black"
        else:
            feedback_style = "bold bright_white on blue"
            
        lines.append(Text(truncated_feedback, style=feedback_style))
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
        lines.append(Text(truncated_prev, style="dim bright_black"))

    # Get shuffle mode once (used in multiple places)
    try:
        shuffle_enabled = playback.get_shuffle_mode()
    except Exception:
        shuffle_enabled = True  # Default to shuffle on error

    # Active playlist info
    active_pl = playlists.get_active_playlist()
    if active_pl:
        playlist_line = f"📋 Playlist: {active_pl['name']}"
        truncated_pl = playlist_line[:console_width - 6] + "..." if len(playlist_line) > console_width - 3 else playlist_line
        lines.append(Text(truncated_pl, style="bold cyan"))

        # Show position if available and in sequential mode
        try:
            saved_position = playback.get_playlist_position(active_pl['id'])

            if saved_position and not shuffle_enabled:
                _, position = saved_position
                # Get total track count (optimized - doesn't fetch full track data)
                total_tracks = playlists.get_playlist_track_count(active_pl['id'])
                position_line = f"   Position: {position + 1}/{total_tracks}"
                lines.append(Text(position_line, style="cyan"))
        except Exception:
            # Gracefully degrade - skip position display on error
            pass

    # Shuffle mode info
    shuffle_icon = "🔀" if shuffle_enabled else "🔁"
    shuffle_text = "Shuffle ON" if shuffle_enabled else "Sequential"
    shuffle_line = f"{shuffle_icon} {shuffle_text}"
    lines.append(Text(shuffle_line, style="bold yellow" if shuffle_enabled else "bold green"))

    # Create panel with all lines
    content = "\n".join(str(line) for line in lines)
    
    # Use full console width for the panel
    panel_width = console_width
    
    panel = Panel(
        content,
        border_style="bold bright_cyan",
        padding=(1, 2),
        width=panel_width,
        height=18,  # Fixed height for consistent space reservation
        expand=True,  # Ensure full width usage
        title="🎵 MUSIC MINION DASHBOARD 🎵",
        title_align="center",
        subtitle="Now Playing",
        subtitle_align="center",
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