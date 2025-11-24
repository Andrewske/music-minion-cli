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
    ('🎵 Playback', 'status', 'ℹ️', 'Show current status'),
    ('🎵 Playback', 'history', '📜', 'Show playback history'),

    # Rating
    ('❤️  Rating', 'love', '❤️', 'Love current track'),
    ('❤️  Rating', 'like', '👍', 'Like current track'),
    ('❤️  Rating', 'unlike', '👎', 'Remove SoundCloud like'),
    ('❤️  Rating', 'archive', '📦', 'Archive track (remove from rotation)'),
    ('❤️  Rating', 'note', '📝', 'Add note to current track'),
    ('❤️  Rating', 'rate', '🎯', 'Pairwise track comparison'),
    ('❤️  Rating', 'rankings', '🏆', 'Show top-rated tracks'),

    # Playlists
    ('📋 Playlists', 'playlist', '📋', 'Browse and select playlists'),
    ('📋 Playlists', 'playlist new', '➕', 'Create new playlist'),
    ('📋 Playlists', 'playlist delete', '🗑️', 'Delete playlist'),
    ('📋 Playlists', 'playlist rename', '✏️', 'Rename playlist'),
    ('📋 Playlists', 'playlist show', '👁️', 'Show playlist tracks'),
    ('📋 Playlists', 'playlist analyze', '📊', 'Analyze playlist'),
    ('📋 Playlists', 'playlist active', '⭐', 'Set active playlist'),
    ('📋 Playlists', 'playlist restart', '🔄', 'Restart playlist'),
    ('📋 Playlists', 'playlist import', '📥', 'Import playlist'),
    ('📋 Playlists', 'playlist export', '📤', 'Export playlist'),
    ('📋 Playlists', 'playlist convert', '🔄', 'Convert playlist format'),
    ('📋 Playlists', 'add', '➕', 'Add current track to playlist'),
    ('📋 Playlists', 'remove', '➖', 'Remove current track from playlist'),

    # Library Management
    ('📚 Library', 'library', '📚', 'Library management'),
    ('📚 Library', 'search', '🔍', 'Search all tracks'),
    ('📚 Library', 'scan', '🔍', 'Scan library for new tracks'),
    ('📚 Library', 'stats', '📊', 'Show library statistics'),
    ('📚 Library', 'metadata', '🔧', 'Edit track metadata'),

    # Library Providers - Switching
    ('📚 Library', 'local', '💿', 'Switch to local library'),
    ('📚 Library', 'soundcloud', '☁️', 'Switch to SoundCloud'),
    ('📚 Library', 'spotify', '🎧', 'Switch to Spotify'),
    ('📚 Library', 'youtube', '📺', 'Switch to YouTube'),

    # Library Providers - Local
    ('📚 Library', 'local auth', '🔐', 'Authenticate local library'),
    ('📚 Library', 'local scan', '🔍', 'Scan local music files'),

    # Library Providers - SoundCloud
    ('📚 Library', 'soundcloud auth', '🔐', 'Authenticate SoundCloud'),
    ('📚 Library', 'soundcloud sync', '🔄', 'Sync SoundCloud library'),

    # Library Providers - Spotify
    ('📚 Library', 'spotify auth', '🔐', 'Authenticate Spotify'),
    ('📚 Library', 'spotify sync', '🔄', 'Sync Spotify library'),
    ('📚 Library', 'spotify device list', '📱', 'List Spotify devices'),
    ('📚 Library', 'spotify device set', '📱', 'Set Spotify device'),
    ('📚 Library', 'spotify device clear', '📱', 'Clear device preference'),

    # Library Providers - YouTube
    ('📚 Library', 'youtube auth', '🔐', 'Authenticate YouTube'),
    ('📚 Library', 'youtube sync', '🔄', 'Sync YouTube library'),

    # AI
    ('🤖 AI', 'ai', '🤖', 'AI-powered features'),
    ('🤖 AI', 'ai setup', '🔧', 'Setup AI features'),
    ('🤖 AI', 'ai analyze', '🔍', 'Analyze current track'),
    ('🤖 AI', 'ai review', '📝', 'Review track tags'),
    ('🤖 AI', 'ai enhance', '✨', 'Enhance metadata'),
    ('🤖 AI', 'ai test', '🧪', 'Test AI features'),
    ('🤖 AI', 'ai usage', '📊', 'Show AI usage stats'),

    # Tags
    ('🏷️  Tags', 'tag', '🏷️', 'Manage track tags'),
    ('🏷️  Tags', 'tag remove', '➖', 'Remove tag from track'),
    ('🏷️  Tags', 'tag list', '📋', 'List all tags'),

    # System
    ('⚙️  System', 'sync', '🔄', 'Context-aware sync'),
    ('⚙️  System', 'migrate', '⬆️', 'Run database migrations'),
    ('⚙️  System', 'killall', '☠️', 'Emergency stop players'),
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
