"""
Dashboard widget - displays current track information and player status
"""

from datetime import datetime
from typing import Optional
from textual.app import ComposeResult
from textual.containers import Container
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static
from rich.text import Text
from rich.panel import Panel

from .state import AppState


# Icon constants with ASCII fallbacks
ICONS = {
    "music": "♪",
    "note": "♫",
    "tag": "🏷️",
    "memo": "📝",
    "star": "⭐",
    "scroll": "📜",
    "heart": "💖",
}


class Dashboard(Static):
    """
    Fixed dashboard display showing current track and player status.
    Uses Textual's reactive system for automatic updates.
    """

    # Reactive properties - automatically trigger re-render when changed
    current_track = reactive("")
    is_playing = reactive(False)
    position = reactive(0.0)
    duration = reactive(0.0)

    def __init__(self, app_state: AppState):
        super().__init__()
        self.app_state = app_state

    def on_mount(self) -> None:
        """Set up update timer"""
        self.set_interval(1.0, self.update_display)

    def update_display(self) -> None:
        """Update display based on current state"""
        # Update reactive properties from state
        # These will automatically trigger a re-render
        player = self.app_state.player
        self.current_track = player.current_track or ""
        self.is_playing = player.is_playing
        self.position = player.current_position
        self.duration = player.duration

        # Force refresh
        self.refresh()

    def render(self) -> Panel:
        """Render the dashboard panel"""
        return self._render_dashboard()

    def _render_dashboard(self) -> Panel:
        """Build and return the dashboard panel"""
        lines = []
        player = self.app_state.player
        metadata = self.app_state.track_metadata
        db_info = self.app_state.track_db_info
        ui_state = self.app_state.ui

        # Header with clock
        current_time = datetime.now().strftime("%H:%M:%S")
        header = Text()
        header.append(f"{ICONS['music']} ", style="bold magenta")
        header.append("MUSIC", style="bold cyan")
        header.append(" ", style="white")
        header.append("MINION", style="bold blue")
        header.append(f" {ICONS['music']}", style="bold magenta")

        # Dynamic spacer
        header_text_len = len(f"{ICONS['music']} MUSIC MINION {ICONS['music']}")
        time_text_len = len(f"[{current_time}]")
        console_width = self.app.console.width if hasattr(self.app, 'console') else 80
        spacer_width = max(console_width - header_text_len - time_text_len - 8, 2)
        header.append(" " * spacer_width)

        # Time with color based on time of day
        hour = datetime.now().hour
        if 6 <= hour < 12:
            time_style = "bold yellow"
        elif 12 <= hour < 18:
            time_style = "bold blue"
        elif 18 <= hour < 22:
            time_style = "bold orange3"
        else:
            time_style = "bold purple"
        header.append(f"[{current_time}]", style=time_style)
        lines.append(header)

        # Colorful separator
        separator_width = console_width - 8
        separator = Text()
        for i in range(separator_width):
            colors = ["cyan", "blue", "magenta", "purple"]
            separator.append("━", style=colors[i % 4])
        lines.append(separator)
        lines.append("")

        # Track information
        if player.current_track and metadata:
            track_lines = self._format_track_display(metadata)
            for i, line in enumerate(track_lines):
                if i == 0:
                    lines.append(Text(line, style="bold white"))
                else:
                    lines.append(Text(line, style="bright_blue"))
        else:
            lines.append(Text(f"{ICONS['note']} No track playing", style="dim"))
            lines.append(Text("  Waiting for music...", style="dim"))

        lines.append("")

        # Progress bar
        if player.is_playing:
            progress = self._create_progress_bar(player.current_position, player.duration)
            lines.append(progress)

            # BPM visualizer
            if metadata and metadata.bpm:
                bpm_line = self._format_bpm_line(metadata.bpm)
                lines.append(bpm_line)
        else:
            lines.append(Text("─" * 40, style="dim"))
            lines.append(Text("⏸ Paused", style="bold yellow on red"))

        lines.append("")

        # Tags and notes
        if db_info:
            tag_lines = self._format_tags_and_notes(db_info.tags, db_info.notes)
            for line in tag_lines:
                if line.startswith(ICONS.get('tag', '#')):
                    lines.append(Text(line, style="bold bright_blue"))
                elif line.startswith(ICONS.get('memo', '>')):
                    lines.append(Text(line, style="italic bright_green"))
                else:
                    lines.append(Text(line, style="blue"))

            # Rating
            if db_info.rating is not None or db_info.last_played:
                rating_line = self._format_rating(db_info.rating, db_info.last_played, db_info.play_count)
                if db_info.rating and db_info.rating >= 80:
                    rating_style = "bold bright_red"
                elif db_info.rating and db_info.rating >= 60:
                    rating_style = "bold bright_yellow"
                elif db_info.rating and db_info.rating <= 20:
                    rating_style = "dim"
                else:
                    rating_style = "white"
                lines.append(Text(rating_line, style=rating_style))

        lines.append("")

        # Feedback or previous track
        if ui_state.should_show_feedback:
            feedback = ui_state.feedback_message
            if feedback:
                if "loved" in feedback.lower() or "❤️" in feedback:
                    style = "bold bright_red on black"
                elif "liked" in feedback.lower() or "👍" in feedback:
                    style = "bold bright_yellow on black"
                elif "archived" in feedback.lower():
                    style = "bold bright_black on red"
                elif "skipped" in feedback.lower():
                    style = "bold cyan on black"
                elif "note" in feedback.lower():
                    style = "bold bright_green on black"
                else:
                    style = "bold bright_white on blue"
                lines.append(Text(feedback, style=style))
        elif ui_state.previous_track:
            prev_line = self._format_previous_track(ui_state.previous_track, ui_state.previous_rating, ui_state.previous_time)
            lines.append(Text(prev_line, style="dim bright_black"))

        # Active playlist info
        playlist_info = self.app_state.playlist
        if playlist_info.name:
            playlist_line = f"📋 Playlist: {playlist_info.name}"
            lines.append(Text(playlist_line, style="bold cyan"))

            if playlist_info.current_position is not None and not ui_state.shuffle_enabled:
                position_line = f"   Position: {playlist_info.current_position + 1}/{playlist_info.track_count}"
                lines.append(Text(position_line, style="cyan"))

        # Shuffle mode
        shuffle_icon = "🔀" if ui_state.shuffle_enabled else "🔁"
        shuffle_text = "Shuffle ON" if ui_state.shuffle_enabled else "Sequential"
        shuffle_line = f"{shuffle_icon} {shuffle_text}"
        lines.append(Text(shuffle_line, style="bold yellow" if ui_state.shuffle_enabled else "bold green"))

        # Create panel
        content = "\n".join(str(line) for line in lines)
        return Panel(
            content,
            border_style="bold bright_cyan",
            padding=(1, 2),
            title="🎵 MUSIC MINION DASHBOARD 🎵",
            title_align="center",
            subtitle="Now Playing",
            subtitle_align="center",
        )

    def _format_track_display(self, metadata) -> list[str]:
        """Format track information for display"""
        lines = []
        lines.append(f"{ICONS['note']} {metadata.title}")
        lines.append(f"  by {metadata.artist}")

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
            lines.append("  " + " ".join(details))

        return lines

    def _create_progress_bar(self, position: float, duration: float) -> Text:
        """Create a colored progress bar"""
        if duration <= 0:
            return Text("─" * 40, style="dim")

        percentage = min(position / duration, 1.0)
        bar_width = 40
        filled = int(bar_width * percentage)

        progress_text = Text()
        for i in range(filled):
            char_percentage = (i + 1) / bar_width
            if char_percentage < 0.33:
                progress_text.append("█", style="green")
            elif char_percentage < 0.66:
                progress_text.append("█", style="yellow")
            else:
                progress_text.append("█", style="red")

        progress_text.append("░" * (bar_width - filled), style="dim")

        # Add time displays
        current = self._format_time(position)
        total = self._format_time(duration)
        progress_text.append(f" {current} ", style="white")
        progress_text.append("━━━━", style="cyan")
        progress_text.append(f" {total}", style="white")

        return progress_text

    def _format_bpm_line(self, bpm: int) -> Text:
        """Format BPM line with color based on tempo"""
        if bpm < 90:
            color = "blue"
        elif bpm < 120:
            color = "cyan"
        elif bpm < 140:
            color = "yellow"
        else:
            color = "red"

        return Text(f"{ICONS['music']} {bpm} BPM {ICONS['music']}", style=f"bold {color}")

    def _format_tags_and_notes(self, tags: list[str], notes: str) -> list[str]:
        """Format tags and notes for display"""
        lines = []

        if tags:
            tag_line = f"{ICONS['tag']}  " + " • ".join(tags[:5])
            lines.append(tag_line)

        if notes:
            if len(notes) > 60:
                notes = notes[:57] + "..."
            lines.append(f"{ICONS['memo']} \"{notes}\"")

        return lines

    def _format_rating(self, rating: Optional[int], last_played: Optional[str], play_count: int) -> str:
        """Format rating and play statistics"""
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

    def _format_previous_track(self, track_info: dict, rating: Optional[str], previous_time: Optional[float]) -> str:
        """Format previous track display"""
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

        time_ago = "just now"
        if previous_time:
            from time import time
            seconds_ago = int(time() - previous_time)
            if seconds_ago < 60:
                time_ago = f"{seconds_ago}s ago"
            else:
                time_ago = f"{seconds_ago // 60} min ago"

        return f"{ICONS['scroll']} Previous: {artist} - {title} ({rating_str} • {time_ago})"

    @staticmethod
    def _format_time(seconds: float) -> str:
        """Format seconds to MM:SS display"""
        if seconds < 0 or seconds > 86400:
            return "--:--"
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}:{secs:02d}"
