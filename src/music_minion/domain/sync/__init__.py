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
    get_sync_status,
    rescan_library,
)

__all__ = [
    "get_file_mtime",
    "write_tags_to_file",
    "read_tags_from_file",
    "detect_file_changes",
    "sync_export",
    "sync_import",
    "get_sync_status",
    "rescan_library",
]
