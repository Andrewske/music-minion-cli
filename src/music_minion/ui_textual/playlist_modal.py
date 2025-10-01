"""
Playlist Browser Modal - Textual implementation
Shows playlists with live preview of tracks and metadata
"""

from textual.app import ComposeResult
from textual.containers import Container, Vertical, Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Input, Static, Label
from textual.binding import Binding
from rich.text import Text
from typing import Optional


class PlaylistModal(ModalScreen[dict]):
    """
    Modal screen for browsing and selecting playlists.

    Features:
    - Two-column layout: list on left, preview on right
    - Live fuzzy search filtering
    - Shows playlist metadata (track count, last played, type)
    - Preview shows top tracks when hovering
    - Keyboard navigation
    """

    CSS = """
    PlaylistModal {
        align: center middle;
    }

    #modal-container {
        width: 90;
        height: auto;
        max-height: 35;
        border: thick $primary;
        padding: 1;
    }

    #search-input {
        margin-bottom: 1;
        border: solid $accent;
    }

    #main-content {
        height: auto;
        max-height: 25;
    }

    #playlist-list {
        width: 45;
        height: 100%;
        border: solid $secondary;
        padding: 1;
    }

    #playlist-preview {
        width: 1fr;
        height: 100%;
        border: solid $secondary;
        padding: 1;
        margin-left: 1;
    }

    .playlist-item {
        padding: 0 1;
        height: auto;
        margin-bottom: 1;
    }

    .playlist-item:hover {
        background: $accent-darken-1;
    }

    .playlist-selected {
        background: $accent;
        color: $text;
    }

    .active-indicator {
        color: $success;
        text-style: bold;
    }

    .preview-title {
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
    }

    .preview-meta {
        color: $text-muted;
        margin-bottom: 1;
    }

    .preview-tracks {
        color: $text;
    }

    #help-text {
        margin-top: 1;
        color: $text-muted;
        text-align: center;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss_none", "Cancel", show=False),
        Binding("up", "cursor_up", "Up", show=False),
        Binding("down", "cursor_down", "Down", show=False),
        Binding("enter", "select", "Select", show=False),
    ]

    def __init__(self, playlists: list[dict], active_playlist_id: Optional[int] = None):
        """
        Initialize playlist modal.

        Args:
            playlists: List of playlist dicts from database
            active_playlist_id: ID of currently active playlist
        """
        super().__init__()
        self.all_playlists = playlists
        self.filtered_playlists = playlists.copy()
        self.active_playlist_id = active_playlist_id
        self.selected_index = 0

        # Find index of active playlist if it exists
        for i, pl in enumerate(self.filtered_playlists):
            if pl['id'] == active_playlist_id:
                self.selected_index = i
                break

    def compose(self) -> ComposeResult:
        """Create child widgets"""
        with Container(id="modal-container"):
            yield Input(
                placeholder="Type to search playlists...",
                id="search-input"
            )

            with Horizontal(id="main-content"):
                # Left: Playlist list
                with VerticalScroll(id="playlist-list"):
                    yield from self._render_playlist_items("")

                # Right: Preview pane
                with Vertical(id="playlist-preview"):
                    yield from self._render_preview()

            yield Label(
                "↑↓ navigate  Enter select  Esc cancel",
                id="help-text"
            )

    def on_mount(self) -> None:
        """Focus the search input on mount"""
        self.query_one("#search-input", Input).focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle search input changes"""
        query = event.value.lower()
        self._update_filtered_playlists(query)
        self._refresh_display()

    def _update_filtered_playlists(self, query: str) -> None:
        """Update filtered playlists based on query"""
        if not query:
            self.filtered_playlists = self.all_playlists.copy()
        else:
            # Fuzzy filter: playlist name contains query
            self.filtered_playlists = [
                pl for pl in self.all_playlists
                if query in pl['name'].lower()
            ]

        # Reset selection to first item
        self.selected_index = 0

    def _render_playlist_items(self, query: str) -> list[Static]:
        """Render playlist items"""
        self._update_filtered_playlists(query)

        widgets = []
        if not self.filtered_playlists:
            widgets.append(Static("No matching playlists", classes="playlist-item"))
            return widgets

        for i, pl in enumerate(self.filtered_playlists):
            # Create playlist item text
            item_text = Text()

            # Active indicator
            if pl['id'] == self.active_playlist_id:
                item_text.append("▶ ", style="green bold")
            else:
                item_text.append("  ", style="")

            # Type emoji
            type_emoji = "📝" if pl['type'] == 'manual' else "🤖"
            item_text.append(f"{type_emoji} ", style="")

            # Playlist name
            name_style = "cyan bold" if i == self.selected_index else "white"
            item_text.append(f"{pl['name']}\n", style=name_style)

            # Metadata line
            meta = Text()
            meta.append(f"  {pl.get('track_count', 0)} tracks", style="dim")

            if pl.get('last_played_at'):
                # Format time ago
                time_ago = self._format_time_ago(pl['last_played_at'])
                meta.append(f" • played {time_ago}", style="dim")

            item_text.append(meta)

            classes = "playlist-item"
            if i == self.selected_index:
                classes += " playlist-selected"

            widgets.append(Static(item_text, classes=classes))

        return widgets

    def _render_preview(self) -> list[Static]:
        """Render preview pane for selected playlist"""
        widgets = []

        if not self.filtered_playlists or self.selected_index >= len(self.filtered_playlists):
            widgets.append(Static("No playlist selected", classes="preview-title"))
            return widgets

        pl = self.filtered_playlists[self.selected_index]

        # Title
        title_text = Text()
        title_text.append(f"📋 {pl['name']}", style="bold cyan")
        widgets.append(Static(title_text, classes="preview-title"))

        # Metadata
        meta_text = Text()
        type_label = "Manual" if pl['type'] == 'manual' else "Smart"
        meta_text.append(f"Type: {type_label}\n", style="dim")
        meta_text.append(f"Tracks: {pl.get('track_count', 0)}\n", style="dim")

        if pl.get('last_played_at'):
            time_ago = self._format_time_ago(pl['last_played_at'])
            meta_text.append(f"Last played: {time_ago}\n", style="dim")

        if pl.get('description'):
            meta_text.append(f"\n{pl['description']}\n", style="")

        widgets.append(Static(meta_text, classes="preview-meta"))

        # Top tracks preview
        if pl.get('track_count', 0) > 0:
            tracks_text = Text()
            tracks_text.append("Top tracks:\n", style="bold")

            # Show first 5 tracks (would need to fetch from database)
            # For now, show placeholder
            tracks_text.append("  (Track preview not yet implemented)\n", style="dim italic")

            widgets.append(Static(tracks_text, classes="preview-tracks"))

        return widgets

    def _refresh_display(self) -> None:
        """Refresh both list and preview"""
        # Refresh playlist list
        playlist_list = self.query_one("#playlist-list", VerticalScroll)
        playlist_list.remove_children()

        query = self.query_one("#search-input", Input).value.lower()
        for widget in self._render_playlist_items(query):
            playlist_list.mount(widget)

        # Refresh preview
        preview_pane = self.query_one("#playlist-preview", Vertical)
        preview_pane.remove_children()

        for widget in self._render_preview():
            preview_pane.mount(widget)

    def action_cursor_up(self) -> None:
        """Move selection up"""
        if self.filtered_playlists:
            self.selected_index = max(0, self.selected_index - 1)
            self._refresh_display()

    def action_cursor_down(self) -> None:
        """Move selection down"""
        if self.filtered_playlists:
            max_index = len(self.filtered_playlists) - 1
            self.selected_index = min(max_index, self.selected_index + 1)
            self._refresh_display()

    def action_select(self) -> None:
        """Select the current playlist"""
        if self.filtered_playlists and 0 <= self.selected_index < len(self.filtered_playlists):
            selected = self.filtered_playlists[self.selected_index]
            self.dismiss(selected)

    def action_dismiss_none(self) -> None:
        """Dismiss without selection"""
        self.dismiss(None)

    @staticmethod
    def _format_time_ago(timestamp: str) -> str:
        """Format timestamp as human-readable time ago"""
        from datetime import datetime, timedelta

        try:
            dt = datetime.fromisoformat(timestamp)
            now = datetime.now()
            diff = now - dt

            if diff < timedelta(minutes=1):
                return "just now"
            elif diff < timedelta(hours=1):
                mins = int(diff.total_seconds() / 60)
                return f"{mins}m ago"
            elif diff < timedelta(days=1):
                hours = int(diff.total_seconds() / 3600)
                return f"{hours}h ago"
            elif diff < timedelta(days=7):
                days = diff.days
                return f"{days}d ago"
            elif diff < timedelta(days=30):
                weeks = diff.days // 7
                return f"{weeks}w ago"
            else:
                months = diff.days // 30
                return f"{months}mo ago"
        except Exception:
            return "unknown"
