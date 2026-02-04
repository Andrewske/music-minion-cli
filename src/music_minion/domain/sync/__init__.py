"""Sync domain - bidirectional metadata synchronization.

This domain handles:
- Reading/writing tags to MP3/M4A files
- File change detection (mtime tracking)
- Export: database → file metadata
- Import: file metadata → database
- Library rescanning with incremental updates
"""

from .engine import (
    get_file_mtime,
    write_tags_to_file,
    read_tags_from_file,
    detect_file_changes,
    sync_export,
    sync_import,
    sync_metadata_export,
    sync_elo_export,
    get_sync_status,
    rescan_library,
    path_similarity,
    detect_missing_and_moved_files,
)

__all__ = [
    "get_file_mtime",
    "write_tags_to_file",
    "read_tags_from_file",
    "detect_file_changes",
    "sync_export",
    "sync_import",
    "sync_metadata_export",
    "sync_elo_export",
    "get_sync_status",
    "rescan_library",
    "path_similarity",
    "detect_missing_and_moved_files",
]
