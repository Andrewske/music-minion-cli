"""
Unified output system using Loguru.
Replaces print() statements and stdlib logging with dual output (console + file).
"""

import sys
from pathlib import Path
from loguru import logger


def setup_loguru(log_file: Path, level: str = "INFO") -> None:
    """
    Configure loguru for file-only logging (blessed UI handles console display).

    Args:
        log_file: Path to log file
        level: Minimum level for file logging (DEBUG, INFO, WARNING, ERROR)
    """
    # Remove default handler
    logger.remove()

    # File output only - no console handler (blessed UI manages display)
    logger.add(
        log_file,
        rotation="10 MB",
        retention=5,  # Keep 5 backup files
        level=level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{line} | {message}",
        enqueue=False,  # Synchronous writes (thread-safe but blocking)
    )

    logger.info(f"Loguru initialized: {log_file} (level={level})")


def log(message: str, level: str = "info") -> None:
    """
    Unified logging: writes to file AND prints for blessed UI.

    Use this instead of print() for user-facing messages that should also be logged.

    Args:
        message: User-facing message (can include emojis, colors, formatting)
        level: Log level (debug, info, warning, error)
    """
    # Log to file via loguru
    log_func = getattr(logger, level)
    log_func(message)

    # Print for blessed UI command history (preserves all formatting)
    print(message)
