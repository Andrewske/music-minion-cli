"""Core infrastructure layer - no business logic dependencies.

This module provides foundation-level services:
- Configuration management (TOML)
- Database operations (SQLite)
- Console management (Rich)

Clean architecture principle: The core layer has no dependencies on
domain or application layers.
"""

# Configuration
from .config import (
    Config,
    load_config,
    save_config,
    get_config_dir,
    get_config_path,
    get_data_dir,
    create_default_config,
    ensure_directories,
)

# Database - Export all public database functions
from .database import (
    get_database_path,
    get_db_connection,
    init_database,
    migrate_database,
    get_or_create_track,
    add_rating,
    add_note,
    start_playback_session,
    end_playback_session,
    get_track_ratings,
    get_track_notes,
    get_recent_ratings,
    get_archived_tracks,
    get_rating_patterns,
    get_library_analytics,
    cleanup_old_sessions,
    get_track_by_path,
    update_ai_processed_note,
    get_unprocessed_notes,
    get_all_tracks,
    get_available_track_paths,
    get_available_tracks,
    db_track_to_library_track,
    add_tags,
    get_track_tags,
    blacklist_tag,
    remove_tag,
    log_ai_request,
    get_ai_usage_stats,
    get_tracks_needing_analysis,
)

# Console
from .console import get_console, safe_print

__all__ = [
    # Config
    "Config",
    "load_config",
    "save_config",
    "get_config_dir",
    "get_config_path",
    "get_data_dir",
    "create_default_config",
    "ensure_directories",
    # Database
    "get_database_path",
    "get_db_connection",
    "init_database",
    "migrate_database",
    "get_or_create_track",
    "add_rating",
    "add_note",
    "start_playback_session",
    "end_playback_session",
    "get_track_ratings",
    "get_track_notes",
    "get_recent_ratings",
    "get_archived_tracks",
    "get_rating_patterns",
    "get_library_analytics",
    "cleanup_old_sessions",
    "get_track_by_path",
    "update_ai_processed_note",
    "get_unprocessed_notes",
    "get_all_tracks",
    "get_available_track_paths",
    "get_available_tracks",
    "db_track_to_library_track",
    "add_tags",
    "get_track_tags",
    "blacklist_tag",
    "remove_tag",
    "log_ai_request",
    "get_ai_usage_stats",
    "get_tracks_needing_analysis",
    # Console
    "get_console",
    "safe_print",
]
