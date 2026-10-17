"""
Cross-cutting utilities for Music Minion.

Contains:
- parsers: Argument and command parsing
"""

from .parsers import parse_command, parse_quoted_args

__all__ = [
    "parse_quoted_args",
    "parse_command",
]
