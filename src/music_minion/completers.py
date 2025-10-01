"""
prompt_toolkit completers for Music Minion CLI
Provides autocomplete functionality for commands and playlists
"""

from typing import Iterable, Dict, Any
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document

from .domain import playlists as playlist_module


# FUTURE ENHANCEMENT: Add custom keybindings
# To add keybindings like Ctrl+P for quick playlist access:
# 1. Create KeyBindings instance in main.py
# 2. Use @kb.add('c-p') decorator for handlers
# 3. Pass kb to PromptSession(key_bindings=kb)
# Example:
#   from prompt_toolkit.key_binding import KeyBindings
#   kb = KeyBindings()
#   @kb.add('c-p')
#   def _(event):
#       event.app.current_buffer.text = 'playlist'
#       event.app.current_buffer.validate_and_handle()


class MusicMinionCompleter(Completer):
    """
    Basic command completer with descriptions.
    Provides autocomplete for all Music Minion commands.

    FUTURE ENHANCEMENTS (Phase 2 - Full Implementation):
    - Context-aware completions based on playback state
    - Intelligent history-based suggestions
    - Inline help text with command examples
    - Dynamic completion based on current track/playlist
    """

    # Command categories for command palette
    # Format: 'command': ('icon', 'description')
    COMMANDS = {
        # Playback commands
        'play': ('▶', 'Start playing music'),
        'pause': ('⏸', 'Pause current track'),
        'resume': ('▸', 'Resume playback'),
        'stop': ('■', 'Stop playback'),
        'skip': ('⏭', 'Skip to next track'),
        'shuffle': ('🔀', 'Toggle shuffle mode'),

        # Rating commands
        'love': ('❤️', 'Love current track'),
        'like': ('👍', 'Like current track'),
        'archive': ('📦', 'Archive track (remove from rotation)'),
        'note': ('📝', 'Add note to current track'),

        # Playlist commands
        'playlist': ('📋', 'Browse and select playlists'),
        'add': ('➕', 'Add current track to playlist'),
        'remove': ('➖', 'Remove current track from playlist'),

        # Library commands
        'scan': ('🔍', 'Scan library for new tracks'),
        'stats': ('📊', 'Show library statistics'),

        # AI commands
        'ai': ('🤖', 'AI-powered features'),

        # Sync commands
        'sync': ('🔄', 'Sync metadata with files'),

        # Tag commands
        'tag': ('🏷️', 'Manage track tags'),

        # System commands
        'help': ('❓', 'Show help'),
        'quit': ('👋', 'Exit Music Minion'),
        'exit': ('👋', 'Exit Music Minion'),
    }

    def get_completions(self, document: Document, complete_event) -> Iterable[Completion]:
        """Generate command completions with descriptions."""
        # Get the word being typed (strip any leading /)
        text = document.text_before_cursor.lstrip('/')
        word = text.lower()

        # Collect matching completions
        matches = []
        for command, (icon, description) in self.COMMANDS.items():
            # Only match against the command name, not the description
            if command.lower().startswith(word):
                matches.append((command, icon, description))

        # Sort and limit to prevent overwhelming display
        matches.sort()
        for command, icon, description in matches[:10]:  # Limit to 10 results
            yield Completion(
                command,
                start_position=-len(text),
                display=command,
                display_meta=f"{icon}\t{description}"
            )


class CommandPaletteCompleter(Completer):
    """
    Categorized command palette completer (triggered by /).
    Shows commands organized by category with rich descriptions.

    FUTURE ENHANCEMENTS (Phase 2):
    - Show recently used commands first
    - Context-aware command suggestions
    - Command aliases and shortcuts
    - Multi-step command wizards
    """

    CATEGORIES = {
        '🎵 Playback': ['play', 'pause', 'resume', 'stop', 'skip', 'shuffle'],
        '❤️  Rating': ['love', 'like', 'archive', 'note'],
        '📋 Playlists': ['playlist', 'add', 'remove'],
        '🔍 Library': ['scan', 'stats', 'sync'],
        '🤖 AI': ['ai'],
        '🏷️  Tags': ['tag'],
        '⚙️  System': ['help', 'quit', 'exit'],
    }

    def get_completions(self, document: Document, complete_event) -> Iterable[Completion]:
        """Generate categorized command completions."""
        text = document.text.lstrip('/')
        word = text.lower()

        # Show all commands organized by category
        # When buffer is just "/" or "/<partial>", show matching commands
        for category, commands in self.CATEGORIES.items():
            for command in commands:
                if not word or command.startswith(word):
                    icon, description = MusicMinionCompleter.COMMANDS.get(command, ('', ''))
                    yield Completion(
                        command,
                        start_position=-len(word),
                        display=f"/{command}",
                        display_meta=f"{icon}\t{description}"
                    )


class PlaylistCompleter(Completer):
    """
    Dynamic playlist completer with fuzzy search.
    Fetches playlists from database and provides smart suggestions.

    FUTURE ENHANCEMENTS (Phase 2):
    - Live preview: Show track count, last played, top artists while browsing
    - Multi-select: Select multiple playlists for batch operations
    - Smart sorting: Recently used playlists first
    - Inline stats: Show BPM range, total duration, etc.
    - Fuzzy matching: Match partial words (e.g., "nye" matches "NYE 2025")
    """

    def get_completions(self, document: Document, complete_event) -> Iterable[Completion]:
        """Generate playlist completions with metadata."""
        word = document.get_word_before_cursor().lower()

        try:
            # Fetch playlists sorted by recently played
            playlists = playlist_module.get_playlists_sorted_by_recent()

            for pl in playlists:
                name = pl['name']
                # Simple fuzzy matching: match if word is in playlist name
                if not word or word in name.lower():
                    # Format metadata
                    type_emoji = "📝" if pl['type'] == 'manual' else "🤖"
                    track_info = f"{pl['track_count']} tracks"

                    # Show last played info if available
                    meta = f"{type_emoji} {pl['type']} | {track_info}"
                    if pl['last_played_at']:
                        from datetime import datetime
                        played_dt = datetime.fromisoformat(pl['last_played_at'])
                        time_ago = _format_time_ago(played_dt)
                        meta += f" | played {time_ago}"

                    yield Completion(
                        name,
                        start_position=-len(word),
                        display=name,
                        display_meta=meta
                    )
        except Exception as e:
            # Graceful degradation - don't break autocomplete
            yield Completion(
                f"Error loading playlists: {e}",
                start_position=-len(word),
                display="[Error]",
                display_meta="Could not load playlists"
            )


def _format_time_ago(dt) -> str:
    """Format datetime as human-readable time ago string."""
    from datetime import datetime, timedelta

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
