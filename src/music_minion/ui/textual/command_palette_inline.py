"""
Inline Command Palette Widget - shows below input field
"""

from textual.app import ComposeResult
from textual.containers import Container, VerticalScroll
from textual.widgets import Input, Static
from textual.widget import Widget
from rich.text import Text


class CommandPaletteInline(Widget):
    """
    Inline command palette that slides up below the input field.

    Features:
    - Live fuzzy filtering as you type
    - Keyboard navigation (↑↓, Enter, Esc)
    - Categorized command display
    - Shows icons and descriptions
    """

    # Command categories
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
        self.visible = False

    def _flatten_commands(self) -> list[tuple[str, str, str, str]]:
        """Flatten commands into (category, command, icon, description) tuples"""
        flat = []
        for category, commands in self.COMMANDS.items():
            for cmd, (icon, desc) in commands.items():
                flat.append((category, cmd, icon, desc))
        return flat

    def compose(self) -> ComposeResult:
        """Create child widgets"""
        with VerticalScroll(id="commands-scroll"):
            # Initial render shows all commands
            yield from self._render_commands("")

    def show_palette(self, query: str = "") -> None:
        """Show the palette with optional initial query"""
        self.visible = True
        self.add_class("visible")
        self._update_filtered_commands(query)
        self._refresh_command_list()

    def hide_palette(self) -> None:
        """Hide the palette"""
        self.visible = False
        self.remove_class("visible")

    def update_filter(self, query: str) -> None:
        """Update filter based on query"""
        self._update_filtered_commands(query)
        self._refresh_command_list()

    def _update_filtered_commands(self, query: str) -> None:
        """Update filtered commands based on query"""
        if not query:
            self.filtered_commands = self.all_commands.copy()
        else:
            # Filter by command name only
            self.filtered_commands = [
                (cat, cmd, icon, desc)
                for cat, cmd, icon, desc in self.all_commands
                if query.lower() in cmd.lower()
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
        try:
            commands_scroll = self.query_one("#commands-scroll", VerticalScroll)
            commands_scroll.remove_children()

            # Render using already filtered commands
            if not self.filtered_commands:
                commands_scroll.mount(Static("No matching commands", classes="command-item"))
                return

            current_category = None
            item_index = 0

            for cat, cmd, icon, desc in self.filtered_commands:
                # Add category header if new category
                if cat != current_category:
                    if current_category is not None:
                        commands_scroll.mount(Static(""))
                    commands_scroll.mount(Static(cat, classes="category-header"))
                    current_category = cat

                # Create command item with highlighting
                item_text = Text()
                item_text.append(f"  {icon} ", style="bold")
                item_text.append(f"{cmd:<20}", style="cyan" if item_index == self.selected_index else "white")
                item_text.append(f" {desc}", style="dim")

                classes = "command-item"
                if item_index == self.selected_index:
                    classes += " command-selected"

                commands_scroll.mount(Static(item_text, classes=classes))
                item_index += 1
        except Exception:
            # Widget not mounted yet
            pass

    def move_selection_up(self) -> None:
        """Move selection up"""
        if self.filtered_commands:
            self.selected_index = max(0, self.selected_index - 1)
            self._refresh_command_list()

    def move_selection_down(self) -> None:
        """Move selection down"""
        if self.filtered_commands:
            max_index = len(self.filtered_commands) - 1
            self.selected_index = min(max_index, self.selected_index + 1)
            self._refresh_command_list()

    def get_selected_command(self) -> str | None:
        """Get the currently selected command"""
        if self.filtered_commands and 0 <= self.selected_index < len(self.filtered_commands):
            _, cmd, _, _ = self.filtered_commands[self.selected_index]
            return cmd
        return None
