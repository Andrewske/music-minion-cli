"""
Centralized logging configuration for Music Minion CLI
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from .config import get_data_dir


def get_log_file_path() -> Path:
    """Get the path to the log file."""
    return get_data_dir() / "music-minion.log"


def setup_logging(
    level: str = "INFO",
    log_file_path: Optional[Path] = None,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
    console_output: bool = False
) -> None:
    """
    Configure centralized logging for the application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file_path: Custom log file path (default: ~/.local/share/music-minion/music-minion.log)
        max_bytes: Maximum size of log file before rotation
        backup_count: Number of backup files to keep
        console_output: Whether to also output logs to console
    """
    log_file = log_file_path if log_file_path else get_log_file_path()
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # Create root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()

    # File handler with rotation
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)  # Capture all levels to file

    # Detailed format for file logs
    file_formatter = logging.Formatter(
        fmt='%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)

    # Optional console handler (for development/debugging)
    if console_output:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(getattr(logging, level.upper(), logging.INFO))

        # Simpler format for console
        console_formatter = logging.Formatter(
            fmt='%(levelname)s: %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)

    # Log the initialization
    root_logger.info(f"Logging initialized: {log_file} (level={level}, max_size={max_bytes}, backups={backup_count})")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a module.

    Args:
        name: Usually __name__ of the calling module

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)
