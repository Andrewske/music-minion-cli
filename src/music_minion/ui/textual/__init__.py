"""
Textual-based UI components for Music Minion CLI

DEPRECATED: This UI is deprecated and will be removed in v1.0.
Please use ui.blessed instead.
"""

import warnings

warnings.warn(
    "ui.textual is deprecated and will be removed in v1.0. "
    "Please use ui.blessed instead.",
    DeprecationWarning,
    stacklevel=2
)

from .app import MusicMinionApp
from .state import AppState
from .runner import MusicMinionRunner

__all__ = ["MusicMinionApp", "AppState", "MusicMinionRunner"]
