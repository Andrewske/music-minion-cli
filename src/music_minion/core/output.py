"""
Unified output system using Loguru.
Replaces print() statements and stdlib logging with dual output (console + file).
"""

import sys
import threading
from pathlib import Path
from typing import Optional, Callable, Any, Dict
from loguru import logger

# Global blessed mode tracking (set when blessed UI starts)
_blessed_mode_active = False
_blessed_ui_callback: Optional[Callable[[Dict[str, Any]], None]] = None
_blessed_mode_lock = threading.Lock()

# Pending history messages queue (for executor to drain after handle_command)
# This fixes race condition where log() updates main loop's ui_state via callback,
# but executor returns its own ui_state that overwrites those updates.
_pending_history_messages: list[tuple[str, str]] = []
_pending_messages_lock = threading.Lock()


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


def set_blessed_mode(
    ui_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
) -> None:
    """
    Enable blessed mode - suppresses stdout printing, routes through UI callback.

    Args:
        ui_callback: Thread-safe callback to update blessed UI state
    """
    global _blessed_mode_active, _blessed_ui_callback
    with _blessed_mode_lock:
        _blessed_mode_active = True
        _blessed_ui_callback = ui_callback
        logger.debug("Blessed mode enabled - log() will route through UI callback")


def clear_blessed_mode() -> None:
    """Disable blessed mode - restores stdout printing."""
    global _blessed_mode_active, _blessed_ui_callback
    with _blessed_mode_lock:
        _blessed_mode_active = False
        _blessed_ui_callback = None
        logger.debug("Blessed mode disabled - log() will print to stdout")


def drain_pending_history_messages() -> list[tuple[str, str]]:
    """
    Get and clear all pending history messages.

    Called by executor after handle_command to get any messages
    that were logged during command execution.

    Returns:
        List of (message, color) tuples
    """
    global _pending_history_messages
    with _pending_messages_lock:
        messages = _pending_history_messages[:]
        _pending_history_messages = []
        return messages


def log(message: str, level: str = "info") -> None:
    """
    Unified logging: writes to file AND prints for blessed UI.

    Use this instead of print() for user-facing messages that should also be logged.

    Routing logic:
    - Blessed mode + silent_logging=False: Route through UI callback (visible in command history)
    - Blessed mode + silent_logging=True: Log to file only (background threads)
    - CLI mode + silent_logging=True: Suppress output (background threads)
    - CLI mode + silent_logging=False: Print to stdout

    Args:
        message: User-facing message (can include emojis, colors, formatting)
        level: Log level (debug, info, warning, error)
    """
    # Log to file via loguru (always)
    log_func = getattr(logger, level)
    log_func(message)

    # Route output based on mode
    with _blessed_mode_lock:
        if _blessed_mode_active:
            # Blessed mode: Check silent_logging flag
            # Background threads with silent_logging=True should not pollute command history
            silent = getattr(threading.current_thread(), "silent_logging", False)
            if not silent:
                # Map log level to color
                color_map = {
                    "debug": "cyan",
                    "info": "white",
                    "warning": "yellow",
                    "error": "red",
                }
                color = color_map.get(level, "white")
                # Add to pending queue instead of calling callback directly
                # This fixes race condition where executor overwrites callback updates
                with _pending_messages_lock:
                    _pending_history_messages.append((message, color))
        else:
            # CLI mode: Check silent_logging flag
            silent = getattr(threading.current_thread(), "silent_logging", False)
            if not silent:
                print(message)
