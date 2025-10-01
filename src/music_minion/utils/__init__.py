"""
Cross-cutting utilities for Music Minion.

Contains:
- autocomplete: CLI autocomplete functionality
- parsers: Argument and command parsing
"""

from .autocomplete import *
from .parsers import *

__all__ = [
    # From autocomplete
    'MusicMinionCompleter',
    'PlaylistCompleter',
    # From parsers
    'parse_quoted_args',
    'parse_command',
]
