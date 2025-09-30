"""
Main Textual application for Music Minion CLI
Implements fixed header dashboard, scrollable command history, and fixed input footer
"""

from textual.app import App, ComposeResult
from textual.containers import Container, VerticalScroll
from textual.widgets import Header, Footer, Input, Static
from textual.binding import Binding
from textual import events

from .dashboard import Dashboard
from .state import AppState
from .command_palette_modal import CommandPaletteModal
from .playlist_modal import PlaylistModal


class CommandHistory(VerticalScroll):
    """Scrollable container for command history and output"""

    def __init__(self):
        super().__init__()
        self.history_items = []

    def add_line(self, text: str, style: str = "white") -> None:
        """Add a line to the command history"""
        self.history_items.append((text, style))
        # Use Rich markup in the Static widget instead of setting styles
        from rich.text import Text
        rich_text = Text(text, style=style)
        line = Static(rich_text)
        self.mount(line)
        # Auto-scroll to bottom
        self.scroll_end(animate=False)

    def clear_history(self) -> None:
        """Clear all history"""
        self.history_items.clear()
        self.remove_children()


class MusicMinionApp(App):
    """
    Main Music Minion Textual application.

    Layout:
    - Fixed top: Dashboard (player status, current track, metadata)
    - Scrollable middle: Command history and output
    - Fixed bottom: Input field and footer with key bindings
    """

    CSS = """
    Dashboard {
        dock: top;
        height: auto;
        max-height: 25;
    }

    #command-history {
        height: 1fr;
        border: solid $secondary;
        padding: 1;
    }

    #input-container {
        dock: bottom;
        height: 3;
        background: $surface;
        padding: 0 1;
    }

    Input {
        width: 1fr;
    }

    Footer {
        dock: bottom;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", show=True),
        Binding("ctrl+l", "clear", "Clear", show=True),
        Binding("/", "command_palette", "Commands", show=True),
    ]

    def __init__(self, app_state: AppState, command_handler: callable):
        """
        Initialize the app.

        Args:
            app_state: Centralized application state
            command_handler: Function to handle commands (command, args) -> bool
        """
        super().__init__()
        self.app_state = app_state
        self.command_handler = command_handler
        self.dashboard = None
        self.command_history = None
        self.input_field = None

    def compose(self) -> ComposeResult:
        """Create child widgets"""
        # Fixed dashboard at top
        self.dashboard = Dashboard(self.app_state)
        yield self.dashboard

        # Scrollable command history in middle
        self.command_history = CommandHistory()
        self.command_history.id = "command-history"
        yield self.command_history

        # Fixed input at bottom
        with Container(id="input-container"):
            self.input_field = Input(placeholder="Type a command or / for menu...")
            yield self.input_field

        # Footer with key bindings
        yield Footer()

    def on_mount(self) -> None:
        """Called when app is mounted"""
        # Focus input field
        self.input_field.focus()

        # Welcome message
        self.command_history.add_line("🎵 Music Minion - Contextual Music Curation", "bold cyan")
        self.command_history.add_line("Type 'help' for commands or '/' for command palette", "dim")
        self.command_history.add_line("", "white")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission"""
        command_text = event.value.strip()

        if not command_text:
            return

        # Add to history
        self.command_history.add_line(f"> {command_text}", "bold green")

        # Clear input
        self.input_field.value = ""

        # Parse and execute command
        parts = command_text.split()
        command = parts[0].lower()
        args = parts[1:] if len(parts) > 1 else []

        # Handle exit commands
        if command in ['quit', 'exit']:
            self.exit()
            return

        # Handle clear command
        if command == 'clear':
            self.action_clear()
            return

        # Delegate to command handler
        try:
            continue_running = self.command_handler(command, args)
            if not continue_running:
                self.exit()
        except Exception as e:
            self.print_output(f"Error: {e}", "red")

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle input changes - check for command palette trigger"""
        if event.value == "/":
            # Clear the "/" from input
            self.input_field.value = ""
            # Show command palette
            self.show_command_palette()

    def print_output(self, text: str, style: str = "white") -> None:
        """Print output to command history"""
        # Split multi-line text
        for line in text.split('\n'):
            self.command_history.add_line(line, style)

    def print_error(self, text: str) -> None:
        """Print error message"""
        self.print_output(f"❌ {text}", "red")

    def print_success(self, text: str) -> None:
        """Print success message"""
        self.print_output(f"✅ {text}", "green")

    def print_info(self, text: str) -> None:
        """Print info message"""
        self.print_output(text, "cyan")

    def action_clear(self) -> None:
        """Clear command history"""
        self.command_history.clear_history()
        self.command_history.add_line("History cleared", "dim")

    def show_command_palette(self) -> None:
        """Show command palette modal"""
        def handle_command_selection(command: str | None) -> None:
            """Handle selected command from palette"""
            if command:
                # Set the command in input field
                self.input_field.value = command
                # Focus input so user can see it and press Enter or add args
                self.input_field.focus()

        # Push the modal screen
        self.push_screen(CommandPaletteModal(), handle_command_selection)

    def action_command_palette(self) -> None:
        """Action for / key binding"""
        self.show_command_palette()

    def show_playlist_browser(self, playlists: list[dict], active_playlist_id: int | None) -> dict | None:
        """
        Show playlist browser modal.
        This is a blocking call that returns the selected playlist.

        Args:
            playlists: List of playlist dicts from database
            active_playlist_id: ID of currently active playlist

        Returns:
            Selected playlist dict or None if cancelled
        """
        result = [None]  # Mutable container to capture result

        def handle_playlist_selection(selected: dict | None) -> None:
            """Handle selected playlist from modal"""
            result[0] = selected

        # Push the modal screen and wait for result
        self.push_screen(PlaylistModal(playlists, active_playlist_id), handle_playlist_selection)

        # Note: In Textual, the callback is called when modal is dismissed
        # The result will be available in the callback
        # For now, we return None and handle selection in the callback
        # The actual handling will be done in the command wrapper
        return None

    def update_player_state(self, player_state) -> None:
        """
        Update player state from external source.
        Called by the main loop to sync MPV state.

        Args:
            player_state: Updated PlayerState object from player module
        """
        self.app_state.player.current_track = player_state.current_track
        self.app_state.player.is_playing = player_state.is_playing
        self.app_state.player.is_paused = player_state.is_paused
        self.app_state.player.current_position = player_state.current_position
        self.app_state.player.duration = player_state.duration
        self.app_state.player.process = player_state.process

        # Dashboard will update automatically via its reactive properties

    def update_track_metadata(self, metadata_dict: dict) -> None:
        """Update current track metadata"""
        from .state import TrackMetadata
        self.app_state.track_metadata = TrackMetadata(
            title=metadata_dict.get("title", "Unknown"),
            artist=metadata_dict.get("artist", "Unknown"),
            album=metadata_dict.get("album"),
            year=metadata_dict.get("year"),
            genre=metadata_dict.get("genre"),
            bpm=metadata_dict.get("bpm"),
            key=metadata_dict.get("key"),
        )

    def update_track_db_info(self, db_info_dict: dict) -> None:
        """Update current track database info"""
        from .state import TrackDBInfo
        self.app_state.track_db_info = TrackDBInfo(
            tags=db_info_dict.get("tags", []),
            notes=db_info_dict.get("notes", ""),
            rating=db_info_dict.get("rating"),
            last_played=db_info_dict.get("last_played"),
            play_count=db_info_dict.get("play_count", 0),
        )

    def update_playlist_info(self, playlist_dict: dict | None) -> None:
        """Update active playlist info"""
        from .state import PlaylistInfo
        if playlist_dict:
            self.app_state.playlist = PlaylistInfo(
                id=playlist_dict.get("id"),
                name=playlist_dict.get("name"),
                type=playlist_dict.get("type", "manual"),
                track_count=playlist_dict.get("track_count", 0),
                current_position=playlist_dict.get("current_position"),
            )
        else:
            self.app_state.playlist = PlaylistInfo()

    def set_shuffle_mode(self, enabled: bool) -> None:
        """Set shuffle mode"""
        self.app_state.ui.shuffle_enabled = enabled
