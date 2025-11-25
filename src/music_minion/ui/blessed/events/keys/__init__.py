"""Keyboard event handlers organized by mode."""

from .utils import parse_key
from .wizard import handle_wizard_key
from .track_viewer import handle_track_viewer_key
from .rating_history import handle_rating_history_key
from .comparison_history import handle_comparison_history_key
from .analytics import handle_analytics_viewer_key
from .metadata_editor import handle_metadata_editor_key
from .comparison import handle_comparison_key
from .normal import handle_normal_mode_key

__all__ = [
    "parse_key",
    "handle_wizard_key",
    "handle_track_viewer_key",
    "handle_rating_history_key",
    "handle_comparison_history_key",
    "handle_analytics_viewer_key",
    "handle_metadata_editor_key",
    "handle_comparison_key",
    "handle_normal_mode_key",
]
