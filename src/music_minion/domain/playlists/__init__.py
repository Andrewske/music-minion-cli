"""Playlists domain - manual/smart playlists with import/export.

This domain handles:
- Playlist CRUD operations (create, delete, rename, etc.)
- Smart playlist filter rules (AND/OR logic, multiple operators)
- AI-powered natural language playlist parsing
- Import from M3U/M3U8/Serato formats
- Export to M3U8/Serato formats with auto-export
"""

# CRUD operations
from .crud import (
    create_playlist,
    update_playlist_track_count,
    delete_playlist,
    rename_playlist,
    get_all_playlists,
    get_playlists_sorted_by_recent,
    get_playlist_by_name,
    get_playlist_by_id,
    get_playlist_tracks,
    get_playlist_track_count,
    add_track_to_playlist,
    remove_track_from_playlist,
    reorder_playlist_track,
    set_active_playlist,
    get_active_playlist,
    clear_active_playlist,
    get_available_playlist_tracks,
)

# Filter operations
from .filters import (
    VALID_FIELDS,
    TEXT_OPERATORS,
    NUMERIC_OPERATORS,
    TEXT_FIELDS,
    NUMERIC_FIELDS,
    validate_filter,
    add_filter,
    remove_filter,
    update_filter,
    get_playlist_filters,
    build_filter_query,
    evaluate_filters,
)

# AI parsing
from .ai_parser import (
    parse_natural_language_to_filters,
    format_filters_for_preview,
    edit_filters_interactive,
)

# Import
from .importers import (
    detect_playlist_format,
    resolve_relative_path,
    import_m3u,
    import_serato_crate,
    import_playlist,
)

# Export
from .exporters import (
    make_relative_path,
    export_m3u8,
    export_serato_crate,
    export_playlist,
    auto_export_playlist,
    export_all_playlists,
)

__all__ = [
    # CRUD
    "create_playlist",
    "update_playlist_track_count",
    "delete_playlist",
    "rename_playlist",
    "get_all_playlists",
    "get_playlists_sorted_by_recent",
    "get_playlist_by_name",
    "get_playlist_by_id",
    "get_playlist_tracks",
    "get_playlist_track_count",
    "add_track_to_playlist",
    "remove_track_from_playlist",
    "reorder_playlist_track",
    "set_active_playlist",
    "get_active_playlist",
    "clear_active_playlist",
    "get_available_playlist_tracks",
    # Filters
    "VALID_FIELDS",
    "TEXT_OPERATORS",
    "NUMERIC_OPERATORS",
    "TEXT_FIELDS",
    "NUMERIC_FIELDS",
    "validate_filter",
    "add_filter",
    "remove_filter",
    "update_filter",
    "get_playlist_filters",
    "build_filter_query",
    "evaluate_filters",
    # AI parsing
    "parse_natural_language_to_filters",
    "format_filters_for_preview",
    "edit_filters_interactive",
    # Import
    "detect_playlist_format",
    "resolve_relative_path",
    "import_m3u",
    "import_serato_crate",
    "import_playlist",
    # Export
    "make_relative_path",
    "export_m3u8",
    "export_serato_crate",
    "export_playlist",
    "auto_export_playlist",
    "export_all_playlists",
]
