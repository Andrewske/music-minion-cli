"""
Configuration management for Music Minion CLI
"""

import os
import tomllib
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass, field


@dataclass
class MusicConfig:
    """Configuration for music library settings."""
    library_paths: List[str] = field(default_factory=lambda: [str(Path.home() / "Music")])
    supported_formats: List[str] = field(default_factory=lambda: [".mp3", ".m4a", ".wav", ".flac"])
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
        valid_formats = {'m3u8', 'crate'}
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


@dataclass
class Config:
    """Main configuration object."""
    music: MusicConfig = field(default_factory=MusicConfig)
    player: PlayerConfig = field(default_factory=PlayerConfig)
    ai: AIConfig = field(default_factory=AIConfig)
    ui: UIConfig = field(default_factory=UIConfig)
    playlists: PlaylistConfig = field(default_factory=PlaylistConfig)
    sync: SyncConfig = field(default_factory=SyncConfig)


def get_config_dir() -> Path:
    """Get the configuration directory path."""
    config_home = os.environ.get("XDG_CONFIG_HOME")
    if config_home:
        return Path(config_home) / "music-minion"
    return Path.home() / ".config" / "music-minion"


def get_config_path() -> Path:
    """Get the main configuration file path.

    Checks for config.toml in the following order:
    1. Current working directory
    2. XDG_CONFIG_HOME/music-minion (or ~/.config/music-minion)
    """
    # Check current directory first
    local_config = Path.cwd() / "config.toml"
    if local_config.exists():
        return local_config

    # Fall back to XDG config directory
    return get_config_dir() / "config.toml"


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
""".strip()


def load_config() -> Config:
    """Load configuration from file or create default."""
    config_path = get_config_path()
    
    if not config_path.exists():
        # Create config directory and default file
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, 'w', encoding='utf-8') as f:
            f.write(create_default_config())
        print(f"Created default configuration at: {config_path}")
        return Config()
    
    try:
        with open(config_path, 'rb') as f:
            toml_data = tomllib.load(f)
        
        # Parse configuration sections
        config = Config()
        
        if 'music' in toml_data:
            music_data = toml_data['music']
            config.music = MusicConfig(
                library_paths=[str(Path(p).expanduser()) for p in music_data.get('library_paths', config.music.library_paths)],
                supported_formats=music_data.get('supported_formats', config.music.supported_formats),
                scan_recursive=music_data.get('scan_recursive', config.music.scan_recursive)
            )
        
        if 'player' in toml_data:
            player_data = toml_data['player']
            config.player = PlayerConfig(
                mpv_socket_path=player_data.get('mpv_socket_path'),
                volume=player_data.get('volume', config.player.volume),
                shuffle_on_start=player_data.get('shuffle_on_start', config.player.shuffle_on_start)
            )
        
        if 'ai' in toml_data:
            ai_data = toml_data['ai']
            config.ai = AIConfig(
                openai_api_key=ai_data.get('openai_api_key'),
                model=ai_data.get('model', config.ai.model),
                auto_process_notes=ai_data.get('auto_process_notes', config.ai.auto_process_notes),
                enabled=ai_data.get('enabled', config.ai.enabled),
                cost_per_1m_input_tokens=ai_data.get('cost_per_1m_input_tokens', config.ai.cost_per_1m_input_tokens),
                cost_per_1m_output_tokens=ai_data.get('cost_per_1m_output_tokens', config.ai.cost_per_1m_output_tokens)
            )
        
        if 'ui' in toml_data:
            ui_data = toml_data['ui']
            config.ui = UIConfig(
                show_progress_bar=ui_data.get('show_progress_bar', config.ui.show_progress_bar),
                show_recent_history=ui_data.get('show_recent_history', config.ui.show_recent_history),
                history_length=ui_data.get('history_length', config.ui.history_length),
                use_colors=ui_data.get('use_colors', config.ui.use_colors),
                enable_dashboard=ui_data.get('enable_dashboard', config.ui.enable_dashboard),
                use_emoji=ui_data.get('use_emoji', config.ui.use_emoji),
                bpm_visualizer=ui_data.get('bpm_visualizer', config.ui.bpm_visualizer),
                refresh_rate=ui_data.get('refresh_rate', config.ui.refresh_rate)
            )

        if 'playlists' in toml_data:
            playlists_data = toml_data['playlists']
            config.playlists = PlaylistConfig(
                auto_export=playlists_data.get('auto_export', config.playlists.auto_export),
                export_formats=playlists_data.get('export_formats', config.playlists.export_formats),
                use_relative_paths=playlists_data.get('use_relative_paths', config.playlists.use_relative_paths)
            )
            # Validate playlist config
            try:
                config.playlists.validate()
            except ValueError as e:
                print(f"Warning: Invalid playlist configuration: {e}")
                print("Using default playlist configuration.")
                config.playlists = PlaylistConfig()

        if 'sync' in toml_data:
            sync_data = toml_data['sync']
            config.sync = SyncConfig(
                auto_sync_on_startup=sync_data.get('auto_sync_on_startup', config.sync.auto_sync_on_startup),
                write_tags_to_metadata=sync_data.get('write_tags_to_metadata', config.sync.write_tags_to_metadata),
                metadata_tag_field=sync_data.get('metadata_tag_field', config.sync.metadata_tag_field),
                tag_prefix=sync_data.get('tag_prefix', config.sync.tag_prefix),
                sync_method=sync_data.get('sync_method', config.sync.sync_method),
                auto_watch_files=sync_data.get('auto_watch_files', config.sync.auto_watch_files)
            )

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
"""

        with open(config_path, 'w', encoding='utf-8') as f:
            f.write(toml_content)
        
        return True
        
    except Exception as e:
        print(f"Error saving configuration to {config_path}: {e}")
        return False


def ensure_directories() -> None:
    """Ensure all necessary directories exist."""
    get_config_dir().mkdir(parents=True, exist_ok=True)
    get_data_dir().mkdir(parents=True, exist_ok=True)