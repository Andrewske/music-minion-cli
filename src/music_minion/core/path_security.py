"""
Path security validation utilities for Music Minion.

Provides pure functions to validate file paths are within allowed library directories,
preventing directory traversal attacks and symlink escapes.
"""

from pathlib import Path
from typing import Optional

from music_minion.core.config import MusicConfig


def is_path_within_library(file_path: Path, library_paths: list[str]) -> bool:
    """Pure function - validates path is within allowed directories.
    
    Uses Path.resolve() to handle symlinks and relative paths, then checks if the
    resolved path is a child of any configured library root directory.
    
    Args:
        file_path: The file path to validate
        library_paths: List of allowed library root paths as strings
        
    Returns:
        True if path is within library boundaries, False otherwise
    """
    try:
        # Resolve symlinks and relative paths to get absolute canonical path
        resolved_path = file_path.resolve()
        
        # Check if resolved path is within any library directory
        for lib_path_str in library_paths:
            lib_path = Path(lib_path_str).resolve()
            try:
                # Use relative_to to check if resolved_path is under lib_path
                resolved_path.relative_to(lib_path)
                return True
            except ValueError:
                # relative_to raises ValueError if path is not a subpath
                continue
        
        return False
    except (OSError, RuntimeError):
        # Path.resolve() can raise OSError for invalid paths or RuntimeError for recursion
        return False


def validate_track_path(file_path: Path, config: MusicConfig) -> Optional[Path]:
    """Pure function - returns validated path or None.
    
    Combines existence check with library boundary validation to ensure
    the path exists and is within allowed library directories.
    
    Args:
        file_path: The file path to validate
        config: Music configuration containing library paths
        
    Returns:
        The validated Path object if valid, None otherwise
    """
    # First check if file exists
    if not file_path.exists():
        return None
    
    # Then check if it's within library boundaries
    if not is_path_within_library(file_path, config.library_paths):
        return None
    
    return file_path
