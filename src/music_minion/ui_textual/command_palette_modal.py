"""
Command Palette Modal - Textual implementation
Shows categorized commands with live fuzzy filtering
"""

from textual.app import ComposeResult
from textual.containers import Container, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Input, Static, Label
from textual.binding import Binding
from rich.text import Text


class CommandPaletteModal(ModalScreen[str]):
    """
    Modal screen for command palette.

    Features:
    - Live fuzzy filtering as you type
    - Keyboard navigation (↑↓, Enter, Esc)
    - Categorized command display
    - Shows icons and descriptions
    """

    CSS = """
    CommandPaletteModal {
        align: center middle;
    }

    #palette-container {
        width: 70;
        height: auto;
        max-height: 30;
        background: $panel;
        border: thick $primary;
        padding: 1;
    }

    #search-input {
        margin-bottom: 1;
        border: solid $accent;
    }

    #commands-list {
        height: auto;
        max-height: 20;
        border: solid $secondary;
    }

    .command-item {
        padding: 0 1;
        height: auto;
    }

    .command-item:hover {
        background: $accent-darken-1;
    }

    .command-selected {
        background: $accent;
        color: $text;
    }

    .category-header {
        color: $primary;
        text-style: bold;
        padding: 1 0 0 0;
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

    # Command categories (from completers.py)
    COMMANDS = {
        '🎵 Playback': {
            'play': ('▶', 'Start playing music'),
            'pause': ('⏸', 'Pause current track'),
            'resume': ('▸', 'Resume playback'),
            'stop': ('■', 'Stop playback'),
            'skip': ('⏭', 'Skip to next track'),
            'shuffle': ('🔀', 'Toggle shuffle mode'),
        },
        '❤️  Rating': {
            'love': ('❤️', 'Love current track'),
            'like': ('👍', 'Like current track'),
            'archive': ('📦', 'Archive track (remove from rotation)'),
            'note': ('📝', 'Add note to current track'),
        },
        '📋 Playlists': {
            'playlist': ('📋', 'Browse and select playlists'),
            'add': ('➕', 'Add current track to playlist'),
            'remove': ('➖', 'Remove current track from playlist'),
        },
        '🔍 Library': {
            'scan': ('🔍', 'Scan library for new tracks'),
            'stats': ('📊', 'Show library statistics'),
            'sync': ('🔄', 'Sync metadata with files'),
        },
        '🤖 AI': {
            'ai': ('🤖', 'AI-powered features'),
        },
        '🏷️  Tags': {
            'tag': ('🏷️', 'Manage track tags'),
        },
        '⚙️  System': {
            'help': ('❓', 'Show help'),
            'quit': ('👋', 'Exit Music Minion'),
            'exit': ('👋', 'Exit Music Minion'),
        },
    }

    def __init__(self):
        super().__init__()
        self.filtered_commands = []
        self.selected_index = 0
        self.all_commands = self._flatten_commands()

    def _flatten_commands(self) -> list[tuple[str, str, str, str]]:
        """Flatten commands into (category, command, icon, description) tuples"""
        flat = []
        for category, commands in self.COMMANDS.items():
            for cmd, (icon, desc) in commands.items():
                flat.append((category, cmd, icon, desc))
        return flat

    def compose(self) -> ComposeResult:
        """Create child widgets"""
        with Container(id="palette-container"):
            yield Input(
                placeholder="Type to filter commands...",
                id="search-input"
            )

            with VerticalScroll(id="commands-list"):
                # Initial render shows all commands
                yield from self._render_commands("")

            yield Label(
                "↑↓ navigate  Enter select  Esc cancel",
                id="help-text"
            )

    def on_mount(self) -> None:
        """Focus the search input on mount"""
        self.query_one("#search-input", Input).focus()
        # Initialize filtered commands
        self._update_filtered_commands("")

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle search input changes"""
        query = event.value.lower()
        self._update_filtered_commands(query)
        self._refresh_command_list()

    def _update_filtered_commands(self, query: str) -> None:
        """Update filtered commands based on query"""
        if not query:
            self.filtered_commands = self.all_commands.copy()
        else:
            # Fuzzy filter: command name contains query
            self.filtered_commands = [
                (cat, cmd, icon, desc)
                for cat, cmd, icon, desc in self.all_commands
                if query in cmd.lower() or query in desc.lower()
            ]

        # Reset selection to first item
        self.selected_index = 0

    def _render_commands(self, query: str) -> list[Static]:
        """Render command items grouped by category"""
        self._update_filtered_commands(query)

        widgets = []
        if not self.filtered_commands:
            widgets.append(Static("No matching commands", classes="command-item"))
            return widgets

        current_category = None
        item_index = 0

        for cat, cmd, icon, desc in self.filtered_commands:
            # Add category header if new category
            if cat != current_category:
                if current_category is not None:
                    # Add spacing between categories
                    widgets.append(Static(""))
                widgets.append(Static(cat, classes="category-header"))
                current_category = cat

            # Create command item with highlighting
            item_text = Text()
            item_text.append(f"  {icon} ", style="bold")
            item_text.append(f"{cmd:<20}", style="cyan" if item_index == self.selected_index else "white")
            item_text.append(f" {desc}", style="dim")

            classes = "command-item"
            if item_index == self.selected_index:
                classes += " command-selected"

            widgets.append(Static(item_text, classes=classes))
            item_index += 1

        return widgets

    def _refresh_command_list(self) -> None:
        """Refresh the command list display"""
        commands_list = self.query_one("#commands-list", VerticalScroll)

        # Remove all children
        commands_list.remove_children()

        # Re-render with current query
        query = self.query_one("#search-input", Input).value.lower()
        for widget in self._render_commands(query):
            commands_list.mount(widget)

    def action_cursor_up(self) -> None:
        """Move selection up"""
        if self.filtered_commands:
            self.selected_index = max(0, self.selected_index - 1)
            self._refresh_command_list()

    def action_cursor_down(self) -> None:
        """Move selection down"""
        if self.filtered_commands:
            # Count actual command items (not category headers)
            max_index = len(self.filtered_commands) - 1
            self.selected_index = min(max_index, self.selected_index + 1)
            self._refresh_command_list()

    def action_select(self) -> None:
        """Select the current command"""
        if self.filtered_commands and 0 <= self.selected_index < len(self.filtered_commands):
            _, cmd, _, _ = self.filtered_commands[self.selected_index]
            self.dismiss(cmd)

    def action_dismiss_none(self) -> None:
        """Dismiss without selection"""
        self.dismiss(None)
