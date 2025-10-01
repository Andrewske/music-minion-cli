"""Centralized Rich Console management.

This module provides a singleton Rich Console instance to avoid circular
dependencies. Previously, modules imported console from main.py, which
created circular import issues.
"""

from rich.console import Console

_console: Console | None = None


def get_console() -> Console:
    """Get or create the global Rich Console instance.

    Returns:
        Console: The global Rich Console instance
    """
    global _console
    if _console is None:
        _console = Console()
    return _console


def safe_print(message: str, style: str | None = None) -> None:
    """Print using Rich Console with optional styling.

    Args:
        message: The message to print
        style: Optional Rich style string (e.g., "bold red", "green")
    """
    console = get_console()
    if style:
        console.print(message, style=style)
    else:
        console.print(message)
