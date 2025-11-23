"""
Configuration management for Music Minion CLI
"""

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class MusicConfig:
    """Configuration for music library settings."""

    library_paths: List[str] = field(
        default_factory=lambda: [str(Path.home() / "Music")]
    )
    supported_formats: List[str] = field(
        default_factory=lambda: [".mp3", ".m4a", ".wav", ".flac"]
    )
    scan_recursive: bool = True


@dataclass
class PlayerConfig:
    """Configuration for music player settings."""

    mpv_socket_path: Optional[str] = None
    volume: int = 50
    shuffle_on_start: bool = True


@dataclass
class AIConfig:
    """Configuration for AI integration."""

    openai_api_key: Optional[str] = None
    model: str = "gpt-4o-mini"
    auto_process_notes: bool = True
    enabled: bool = False
    # API pricing per 1M tokens (in USD)
    cost_per_1m_input_tokens: float = 0.15
    cost_per_1m_output_tokens: float = 0.60


@dataclass
class UIConfig:
    """Configuration for user interface."""

    show_progress_bar: bool = True
    show_recent_history: bool = True
    history_length: int = 10
    use_colors: bool = True
    enable_dashboard: bool = True
    use_emoji: bool = True
    bpm_visualizer: bool = True
    refresh_rate: int = 1


@dataclass
class PlaylistConfig:
    """Configuration for playlist export and sync."""

    auto_export: bool = True
    export_formats: List[str] = field(default_factory=lambda: ["m3u8", "crate"])
    use_relative_paths: bool = True

    def validate(self) -> None:
        """Validate playlist configuration values.

        Raises:
            ValueError: If configuration values are invalid
        """
        valid_formats = {"m3u8", "crate"}
        invalid_formats = set(self.export_formats) - valid_formats
        if invalid_formats:
            raise ValueError(
                f"Invalid export formats: {invalid_formats}. "
                f"Valid formats are: {valid_formats}"
            )


@dataclass
class SyncConfig:
    """Configuration for metadata sync and file watching."""

    auto_sync_on_startup: bool = True
    write_tags_to_metadata: bool = True
    metadata_tag_field: str = "COMMENT"  # Field to store tags (COMMENT or custom)
    tag_prefix: str = "mm:"  # Prefix for Music Minion tags in metadata
    sync_method: str = "manual"  # 'manual' or 'syncthing' (future)
    auto_watch_files: bool = False  # Watch for file changes (future)
    playlist_sync_ttl_seconds: int = 600  # TTL for playlist sync cache


@dataclass
class LoggingConfig:
    """Configuration for logging."""

    level: str = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    log_file: Optional[str] = (
        None  # Custom log file path (default: ~/.local/share/music-minion/music-minion.log)
    )
    max_file_size_mb: int = 10  # Maximum log file size before rotation
    backup_count: int = 5  # Number of backup files to keep
    console_output: bool = False  # Also output to console (for debugging)


@dataclass
class SoundCloudConfig:
    """Configuration for SoundCloud provider integration."""

    enabled: bool = False
    client_id: str = ""
    client_secret: str = ""
    redirect_uri: str = "http://localhost:8080/callback"
    sync_likes: bool = True
    sync_playlists: bool = True


@dataclass
class SpotifyConfig:
    """Configuration for Spotify provider integration."""

    enabled: bool = False
    client_id: str = ""
    client_secret: str = ""
    redirect_uri: str = "http://localhost:8080/callback"
    sync_likes: bool = True
    sync_playlists: bool = True
    preferred_device_id: str = ""
    preferred_device_name: str = ""


@dataclass
class IPCConfig:
    """Configuration for IPC (Inter-Process Communication)."""

    enabled: bool = True


@dataclass
class NotificationsConfig:
    """Configuration for desktop notifications."""

    enabled: bool = True
    show_success: bool = True
    show_errors: bool = True


@dataclass
class HotkeysConfig:
    """Configuration for hotkey shortcuts."""

    dated_playlist_template: str = "{month} {year}"  # e.g., "Nov 25"
    not_quite_playlist: str = "Not Quite"
    not_interested_playlist: str = "Not Interested"


@dataclass
class Config:
    """Main configuration object."""

    music: MusicConfig = field(default_factory=MusicConfig)
    player: PlayerConfig = field(default_factory=PlayerConfig)
    ai: AIConfig = field(default_factory=AIConfig)
    ui: UIConfig = field(default_factory=UIConfig)
    playlists: PlaylistConfig = field(default_factory=PlaylistConfig)
    sync: SyncConfig = field(default_factory=SyncConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    soundcloud: SoundCloudConfig = field(default_factory=SoundCloudConfig)
    spotify: SpotifyConfig = field(default_factory=SpotifyConfig)
    ipc: IPCConfig = field(default_factory=IPCConfig)
    notifications: NotificationsConfig = field(default_factory=NotificationsConfig)
    hotkeys: HotkeysConfig = field(default_factory=HotkeysConfig)


def get_config_dir() -> Path:
    """Get the configuration directory path."""
    config_home = os.environ.get("XDG_CONFIG_HOME")
    if config_home:
        return Path(config_home) / "music-minion"
    return Path.home() / ".config" / "music-minion"


def _find_project_config() -> Optional[Path]:
    """Find config.toml in project root by looking for pyproject.toml.

    This is used during development to automatically find the project's config file
    even when the app is run via 'uv run' which may change the working directory.

    Returns:
        Path to config.toml in project root, or None if not found
    """
    try:
        # Start from this file's location
        current = Path(__file__).resolve().parent
        # Walk up to find pyproject.toml (marker for project root)
        for parent in [current] + list(current.parents):
            if (parent / "pyproject.toml").exists():
                config_path = parent / "config.toml"
                if config_path.exists():
                    return config_path
                # Found project root but no config.toml there
                return None
    except Exception:
        # If anything goes wrong, just return None
        pass
    return None


def get_config_path() -> Path:
    """Get the main configuration file path.

    Checks for config.toml in the following order:
    1. Project root (detected via pyproject.toml) - for development
    2. Current working directory
    3. XDG_CONFIG_HOME/music-minion (or ~/.config/music-minion)
    """
    # Check for project root config (development mode)
    project_config = _find_project_config()
    if project_config:
        return project_config

    # Check current directory
    local_config = Path.cwd() / "config.toml"
    if local_config.exists():
        return local_config

    # Fall back to XDG config directory
    global_config = get_config_dir() / "config.toml"
    return global_config


def get_data_dir() -> Path:
    """Get the data directory path."""
    data_home = os.environ.get("XDG_DATA_HOME")
    if data_home:
        return Path(data_home) / "music-minion"
    return Path.home() / ".local" / "share" / "music-minion"


def create_default_config() -> str:
    """Create a default configuration TOML content."""
    return """
# Music Minion CLI Configuration

[music]
# Paths to scan for music files
library_paths = ["~/Music"]

# Supported audio file formats
supported_formats = [".mp3", ".m4a", ".wav", ".flac"]

# Recursively scan subdirectories
scan_recursive = true

[player]
# Path for mpv socket (auto-detected if not specified)
# mpv_socket_path = "/tmp/mpv-socket"

# Default volume (0-100)
volume = 50

# Start in shuffle mode
shuffle_on_start = true

[ai]
# OpenAI API key for note processing (optional)
# openai_api_key = "your-api-key-here"

# AI model to use
model = "gpt-4o-mini"

# Automatically process notes after songs
auto_process_notes = true

# Enable AI features
enabled = false

# API pricing per 1M tokens (in USD) - adjust based on OpenAI pricing
cost_per_1m_input_tokens = 0.15
cost_per_1m_output_tokens = 0.60

[ui]
# Show progress bar for current song
show_progress_bar = true

# Show recent song history
show_recent_history = true

# Number of recent songs to display
history_length = 10

# Use colors in terminal output
use_colors = true

# Enable rich dashboard UI (disable for simple mode)
enable_dashboard = true

# Use emoji in UI (disable for ASCII-only)
use_emoji = true

# Show BPM visualizer animation
bpm_visualizer = true

# Dashboard refresh rate in Hz
refresh_rate = 1

[playlists]
# Auto-export playlists when they are modified
auto_export = true

# Formats to export (m3u8, crate)
export_formats = ["m3u8", "crate"]

# Use relative paths for M3U8 files (for cross-platform compatibility)
use_relative_paths = true

[sync]
# Auto-sync file metadata on startup
auto_sync_on_startup = true

# Write tags to file metadata
write_tags_to_metadata = true

# Metadata field to use for tags (COMMENT is standard)
metadata_tag_field = "COMMENT"

# Prefix for Music Minion tags in metadata
tag_prefix = "mm:"

# Sync method (manual or syncthing)
sync_method = "manual"

# Auto-watch files for changes (future feature)
auto_watch_files = false

[logging]
# Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
level = "INFO"

# Custom log file path (default: ~/.local/share/music-minion/music-minion.log)
# log_file = "/path/to/custom/music-minion.log"

# Maximum log file size in MB before rotation
max_file_size_mb = 10

# Number of backup log files to keep
backup_count = 5

# Also output logs to console (useful for debugging)
console_output = false

[soundcloud]
# Enable SoundCloud integration
enabled = false

# SoundCloud API credentials (get from https://developers.soundcloud.com/docs/api/guide#authentication)
# Register an app at: https://soundcloud.com/you/apps/new
# Uncomment and set your credentials:
# client_id = "your-client-id-here"
# client_secret = "your-client-secret-here"

# OAuth redirect URI (must match your app settings)
redirect_uri = "http://localhost:8080/callback"

# Sync user's liked tracks
sync_likes = true

# Sync user's playlists
sync_playlists = true

[ipc]
# Enable IPC (Inter-Process Communication) for external commands
enabled = true

[notifications]
# Enable desktop notifications
enabled = true

# Show success notifications
show_success = true

# Show error notifications
show_errors = true

[hotkeys]
# Template for dated playlists (e.g., "Nov 25", "Dec 25")
dated_playlist_template = "{month} {year}"

# Playlist name for "Not Quite" workflow
not_quite_playlist = "Not Quite"

# Playlist name for "Not Interested" workflow
not_interested_playlist = "Not Interested"
""".strip()


def load_config() -> Config:
    """Load configuration from file or create default.

    Environment variables override TOML values:
    - SOUNDCLOUD_CLIENT_ID
    - SOUNDCLOUD_CLIENT_SECRET
    """
    # Load .env file from config directory if it exists
    from dotenv import load_dotenv

    env_path = get_config_dir() / ".env"
    if env_path.exists():
        load_dotenv(env_path)

    config_path = get_config_path()

    if not config_path.exists():
        # Create config directory and default file
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(create_default_config())
        print(f"Created default configuration at: {config_path}")
        return Config()

    try:
        with open(config_path, "rb") as f:
            toml_data = tomllib.load(f)

        # Parse configuration sections
        config = Config()

        if "music" in toml_data:
            music_data = toml_data["music"]
            config.music = MusicConfig(
                library_paths=[
                    str(Path(p).expanduser())
                    for p in music_data.get("library_paths", config.music.library_paths)
                ],
                supported_formats=music_data.get(
                    "supported_formats", config.music.supported_formats
                ),
                scan_recursive=music_data.get(
                    "scan_recursive", config.music.scan_recursive
                ),
            )

        if "player" in toml_data:
            player_data = toml_data["player"]
            config.player = PlayerConfig(
                mpv_socket_path=player_data.get("mpv_socket_path"),
                volume=player_data.get("volume", config.player.volume),
                shuffle_on_start=player_data.get(
                    "shuffle_on_start", config.player.shuffle_on_start
                ),
            )

        if "ai" in toml_data:
            ai_data = toml_data["ai"]
            config.ai = AIConfig(
                openai_api_key=ai_data.get("openai_api_key"),
                model=ai_data.get("model", config.ai.model),
                auto_process_notes=ai_data.get(
                    "auto_process_notes", config.ai.auto_process_notes
                ),
                enabled=ai_data.get("enabled", config.ai.enabled),
                cost_per_1m_input_tokens=ai_data.get(
                    "cost_per_1m_input_tokens", config.ai.cost_per_1m_input_tokens
                ),
                cost_per_1m_output_tokens=ai_data.get(
                    "cost_per_1m_output_tokens", config.ai.cost_per_1m_output_tokens
                ),
            )

        if "ui" in toml_data:
            ui_data = toml_data["ui"]
            config.ui = UIConfig(
                show_progress_bar=ui_data.get(
                    "show_progress_bar", config.ui.show_progress_bar
                ),
                show_recent_history=ui_data.get(
                    "show_recent_history", config.ui.show_recent_history
                ),
                history_length=ui_data.get("history_length", config.ui.history_length),
                use_colors=ui_data.get("use_colors", config.ui.use_colors),
                enable_dashboard=ui_data.get(
                    "enable_dashboard", config.ui.enable_dashboard
                ),
                use_emoji=ui_data.get("use_emoji", config.ui.use_emoji),
                bpm_visualizer=ui_data.get("bpm_visualizer", config.ui.bpm_visualizer),
                refresh_rate=ui_data.get("refresh_rate", config.ui.refresh_rate),
            )

        if "playlists" in toml_data:
            playlists_data = toml_data["playlists"]
            config.playlists = PlaylistConfig(
                auto_export=playlists_data.get(
                    "auto_export", config.playlists.auto_export
                ),
                export_formats=playlists_data.get(
                    "export_formats", config.playlists.export_formats
                ),
                use_relative_paths=playlists_data.get(
                    "use_relative_paths", config.playlists.use_relative_paths
                ),
            )
            # Validate playlist config
            try:
                config.playlists.validate()
            except ValueError as e:
                print(f"Warning: Invalid playlist configuration: {e}")
                print("Using default playlist configuration.")
                config.playlists = PlaylistConfig()

        if "sync" in toml_data:
            sync_data = toml_data["sync"]
            config.sync = SyncConfig(
                auto_sync_on_startup=sync_data.get(
                    "auto_sync_on_startup", config.sync.auto_sync_on_startup
                ),
                write_tags_to_metadata=sync_data.get(
                    "write_tags_to_metadata", config.sync.write_tags_to_metadata
                ),
                metadata_tag_field=sync_data.get(
                    "metadata_tag_field", config.sync.metadata_tag_field
                ),
                tag_prefix=sync_data.get("tag_prefix", config.sync.tag_prefix),
                sync_method=sync_data.get("sync_method", config.sync.sync_method),
                auto_watch_files=sync_data.get(
                    "auto_watch_files", config.sync.auto_watch_files
                ),
            )

        if "logging" in toml_data:
            logging_data = toml_data["logging"]
            log_file = logging_data.get("log_file")
            if log_file:
                log_file = str(Path(log_file).expanduser())
            config.logging = LoggingConfig(
                level=logging_data.get("level", config.logging.level).upper(),
                log_file=log_file,
                max_file_size_mb=logging_data.get(
                    "max_file_size_mb", config.logging.max_file_size_mb
                ),
                backup_count=logging_data.get(
                    "backup_count", config.logging.backup_count
                ),
                console_output=logging_data.get(
                    "console_output", config.logging.console_output
                ),
            )

        if "soundcloud" in toml_data:
            soundcloud_data = toml_data["soundcloud"]
            config.soundcloud = SoundCloudConfig(
                enabled=soundcloud_data.get("enabled", config.soundcloud.enabled),
                client_id=soundcloud_data.get("client_id", config.soundcloud.client_id),
                client_secret=soundcloud_data.get(
                    "client_secret", config.soundcloud.client_secret
                ),
                redirect_uri=soundcloud_data.get(
                    "redirect_uri", config.soundcloud.redirect_uri
                ),
                sync_likes=soundcloud_data.get(
                    "sync_likes", config.soundcloud.sync_likes
                ),
                sync_playlists=soundcloud_data.get(
                    "sync_playlists", config.soundcloud.sync_playlists
                ),
            )

        # Override SoundCloud credentials with environment variables if present
        soundcloud_client_id = os.environ.get("SOUNDCLOUD_CLIENT_ID")
        soundcloud_client_secret = os.environ.get("SOUNDCLOUD_CLIENT_SECRET")

        if soundcloud_client_id:
            config.soundcloud.client_id = soundcloud_client_id
        if soundcloud_client_secret:
            config.soundcloud.client_secret = soundcloud_client_secret

        if "spotify" in toml_data:
            spotify_data = toml_data["spotify"]
            config.spotify = SpotifyConfig(
                enabled=spotify_data.get("enabled", config.spotify.enabled),
                client_id=spotify_data.get("client_id", config.spotify.client_id),
                client_secret=spotify_data.get(
                    "client_secret", config.spotify.client_secret
                ),
                redirect_uri=spotify_data.get(
                    "redirect_uri", config.spotify.redirect_uri
                ),
                sync_likes=spotify_data.get("sync_likes", config.spotify.sync_likes),
                sync_playlists=spotify_data.get(
                    "sync_playlists", config.spotify.sync_playlists
                ),
                preferred_device_id=spotify_data.get(
                    "preferred_device_id", config.spotify.preferred_device_id
                ),
                preferred_device_name=spotify_data.get(
                    "preferred_device_name", config.spotify.preferred_device_name
                ),
            )

        # Override Spotify credentials with environment variables if present
        spotify_client_id = os.environ.get("SPOTIFY_CLIENT_ID")
        spotify_client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET")

        if spotify_client_id:
            config.spotify.client_id = spotify_client_id
        if spotify_client_secret:
            config.spotify.client_secret = spotify_client_secret

        return config

    except Exception as e:
        print(f"Error loading configuration from {config_path}: {e}")
        print("Using default configuration.")
        return Config()


def save_config(config: Config) -> bool:
    """Save configuration to file."""
    config_path = get_config_path()

    try:
        # Create config directory if it doesn't exist
        config_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert config to TOML format
        toml_content = f"""# Music Minion CLI Configuration

[music]
library_paths = {config.music.library_paths!r}
supported_formats = {config.music.supported_formats!r}
scan_recursive = {config.music.scan_recursive!r}

[player]
volume = {config.player.volume}
shuffle_on_start = {config.player.shuffle_on_start!r}"""

        if config.player.mpv_socket_path:
            toml_content += f'\nmpv_socket_path = "{config.player.mpv_socket_path}"'

        toml_content += f"""

[ai]
model = "{config.ai.model}"
auto_process_notes = {config.ai.auto_process_notes!r}
enabled = {config.ai.enabled!r}
cost_per_1m_input_tokens = {config.ai.cost_per_1m_input_tokens}
cost_per_1m_output_tokens = {config.ai.cost_per_1m_output_tokens}"""

        if config.ai.openai_api_key:
            toml_content += f'\nopenai_api_key = "{config.ai.openai_api_key}"'

        toml_content += f"""

[ui]
show_progress_bar = {config.ui.show_progress_bar!r}
show_recent_history = {config.ui.show_recent_history!r}
history_length = {config.ui.history_length}
use_colors = {config.ui.use_colors!r}
enable_dashboard = {config.ui.enable_dashboard!r}
use_emoji = {config.ui.use_emoji!r}
bpm_visualizer = {config.ui.bpm_visualizer!r}
refresh_rate = {config.ui.refresh_rate}

[playlists]
auto_export = {config.playlists.auto_export!r}
export_formats = {config.playlists.export_formats!r}
use_relative_paths = {config.playlists.use_relative_paths!r}

[sync]
auto_sync_on_startup = {config.sync.auto_sync_on_startup!r}
write_tags_to_metadata = {config.sync.write_tags_to_metadata!r}
metadata_tag_field = "{config.sync.metadata_tag_field}"
tag_prefix = "{config.sync.tag_prefix}"
sync_method = "{config.sync.sync_method}"
auto_watch_files = {config.sync.auto_watch_files!r}

[logging]
level = "{config.logging.level}"
max_file_size_mb = {config.logging.max_file_size_mb}
backup_count = {config.logging.backup_count}
console_output = {config.logging.console_output!r}"""

        if config.logging.log_file:
            toml_content += f'\nlog_file = "{config.logging.log_file}"'

        toml_content += f"""

[soundcloud]
enabled = {config.soundcloud.enabled!r}
redirect_uri = "{config.soundcloud.redirect_uri}"
sync_likes = {config.soundcloud.sync_likes!r}
sync_playlists = {config.soundcloud.sync_playlists!r}"""

        if config.soundcloud.client_id:
            toml_content += f'\nclient_id = "{config.soundcloud.client_id}"'
        if config.soundcloud.client_secret:
            toml_content += f'\nclient_secret = "{config.soundcloud.client_secret}"'

        toml_content += f"""

[spotify]
enabled = {config.spotify.enabled!r}
redirect_uri = "{config.spotify.redirect_uri}"
sync_likes = {config.spotify.sync_likes!r}
sync_playlists = {config.spotify.sync_playlists!r}"""

        if config.spotify.preferred_device_id:
            toml_content += (
                f'\npreferred_device_id = "{config.spotify.preferred_device_id}"'
            )
        if config.spotify.preferred_device_name:
            toml_content += (
                f'\npreferred_device_name = "{config.spotify.preferred_device_name}"'
            )

        if config.spotify.client_id:
            toml_content += f'\nclient_id = "{config.spotify.client_id}"'
        if config.spotify.client_secret:
            toml_content += f'\nclient_secret = "{config.spotify.client_secret}"'

        toml_content += "\n"

        with open(config_path, "w", encoding="utf-8") as f:
            f.write(toml_content)

        return True

    except Exception as e:
        print(f"Error saving configuration to {config_path}: {e}")
        return False


def ensure_directories() -> None:
    """Ensure all necessary directories exist."""
    get_config_dir().mkdir(parents=True, exist_ok=True)
    get_data_dir().mkdir(parents=True, exist_ok=True)
