"""Layout calculation functions."""

from blessed import Terminal
from ..state import UIState


def calculate_layout(term: Terminal, state: UIState, dashboard_height: int) -> dict[str, int]:
    """
    Pure function: calculate y-positions for all regions.

    Args:
        term: blessed Terminal instance
        state: Current UI state
        dashboard_height: Actual height of rendered dashboard

    Returns:
        Dictionary with region positions and heights
    """
    input_height = 3
    # Allocate height for palette, wizard, track viewer, rating history, comparison history, analytics viewer, comparison, or editor (mutually exclusive)
    overlay_height = 0
    if state.palette_visible or state.wizard_active:
        overlay_height = 22
    elif state.builder.active:
        overlay_height = 22
    elif state.track_viewer_visible:
        overlay_height = 22
    elif state.rating_history_visible:
        overlay_height = 22
    elif state.comparison_history_visible:
        overlay_height = 22
    elif state.analytics_viewer_visible:
        # Analytics viewer needs more space - use most of available screen
        available = term.height - dashboard_height - input_height
        min_history = 3  # Keep minimal history visible for context
        overlay_height = max(30, available - min_history)
    elif state.comparison.active:
        overlay_height = 22
    elif state.editor_visible:
        overlay_height = 22

    return {
        'dashboard_y': 0,
        'dashboard_height': dashboard_height,
        'history_y': dashboard_height,
        'history_height': term.height - dashboard_height - input_height - overlay_height,
        'input_y': term.height - input_height - overlay_height,
        'palette_y': term.height - overlay_height,
        'palette_height': overlay_height,
        'track_viewer_y': term.height - overlay_height,
        'track_viewer_height': overlay_height,
        'analytics_viewer_y': term.height - overlay_height,
        'analytics_viewer_height': overlay_height,
    }
