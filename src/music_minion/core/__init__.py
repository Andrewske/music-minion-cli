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
    get_config_dir,
    get_data_dir,
    setup_config,
    save_api_key,
    load_api_key,
)

# Database - Export all public database functions
from .database import (
    SCHEMA_VERSION,
    get_database_path,
    get_db_connection,
    init_database,
    migrate_database,
    add_track,
    get_track_by_path,
    get_all_tracks,
    update_track_metadata,
    delete_track,
    add_rating,
    get_ratings,
    add_note,
    get_notes,
    get_track_notes,
    add_tags,
    get_tags,
    get_track_tags,
    remove_tag,
    log_ai_request,
    get_ai_stats,
    db_track_to_library_track,
)

# Console
from .console import get_console, safe_print

__all__ = [
    # Config
    "Config",
    "load_config",
    "get_config_dir",
    "get_data_dir",
    "setup_config",
    "save_api_key",
    "load_api_key",
    # Database
    "SCHEMA_VERSION",
    "get_database_path",
    "get_db_connection",
    "init_database",
    "migrate_database",
    "add_track",
    "get_track_by_path",
    "get_all_tracks",
    "update_track_metadata",
    "delete_track",
    "add_rating",
    "get_ratings",
    "add_note",
    "get_notes",
    "get_track_notes",
    "add_tags",
    "get_tags",
    "get_track_tags",
    "remove_tag",
    "log_ai_request",
    "get_ai_stats",
    "db_track_to_library_track",
    # Console
    "get_console",
    "safe_print",
]
