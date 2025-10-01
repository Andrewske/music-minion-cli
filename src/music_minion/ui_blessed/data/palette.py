"""Command palette data and filtering."""

# Command definitions: (category, command, icon, description)
COMMAND_DEFINITIONS: list[tuple[str, str, str, str]] = [
    # Playback
    ('🎵 Playback', 'play', '▶', 'Start playing music'),
    ('🎵 Playback', 'pause', '⏸', 'Pause current track'),
    ('🎵 Playback', 'resume', '▸', 'Resume playback'),
    ('🎵 Playback', 'stop', '■', 'Stop playback'),
    ('🎵 Playback', 'skip', '⏭', 'Skip to next track'),
    ('🎵 Playback', 'shuffle', '🔀', 'Toggle shuffle mode'),

    # Rating
    ('❤️  Rating', 'love', '❤️', 'Love current track'),
    ('❤️  Rating', 'like', '👍', 'Like current track'),
    ('❤️  Rating', 'archive', '📦', 'Archive track (remove from rotation)'),
    ('❤️  Rating', 'note', '📝', 'Add note to current track'),

    # Playlists
    ('📋 Playlists', 'playlist', '📋', 'Browse and select playlists'),
    ('📋 Playlists', 'add', '➕', 'Add current track to playlist'),
    ('📋 Playlists', 'remove', '➖', 'Remove current track from playlist'),

    # Library
    ('🔍 Library', 'scan', '🔍', 'Scan library for new tracks'),
    ('🔍 Library', 'stats', '📊', 'Show library statistics'),
    ('🔍 Library', 'sync', '🔄', 'Sync metadata with files'),

    # AI
    ('🤖 AI', 'ai', '🤖', 'AI-powered features'),

    # Tags
    ('🏷️  Tags', 'tag', '🏷️', 'Manage track tags'),

    # System
    ('⚙️  System', 'help', '❓', 'Show help'),
    ('⚙️  System', 'quit', '👋', 'Exit Music Minion'),
    ('⚙️  System', 'exit', '👋', 'Exit Music Minion'),
]


def filter_commands(
    query: str,
    all_commands: list[tuple[str, str, str, str]] | None = None
) -> list[tuple[str, str, str, str]]:
    """
    Filter commands by query string.

    Args:
        query: Search query (without leading "/")
        all_commands: All available commands (defaults to COMMAND_DEFINITIONS)

    Returns:
        Filtered list of (category, command, icon, description) tuples
    """
    if all_commands is None:
        all_commands = COMMAND_DEFINITIONS

    if not query:
        return all_commands.copy()

    # Filter by command name only
    query_lower = query.lower()
    return [
        (cat, cmd, icon, desc)
        for cat, cmd, icon, desc in all_commands
        if query_lower in cmd.lower()
    ]
