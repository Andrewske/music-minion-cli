"""Command execution and handlers.

This package contains command execution logic and specialized handlers for
different command types (playlists, track viewer, wizard).
"""

from .executor import execute_command, parse_command_line

__all__ = ['execute_command', 'parse_command_line']
