"""Layout calculation functions."""

from blessed import Terminal
from ..state import UIState


def calculate_layout(term: Terminal, state: UIState) -> dict[str, int]:
    """
    Pure function: calculate y-positions for all regions.

    Args:
        term: blessed Terminal instance
        state: Current UI state

    Returns:
        Dictionary with region positions and heights
    """
    dashboard_height = 20
    input_height = 3
    palette_height = 22 if state.palette_visible else 0

    return {
        'dashboard_y': 0,
        'dashboard_height': dashboard_height,
        'history_y': dashboard_height,
        'history_height': term.height - dashboard_height - input_height - palette_height,
        'input_y': term.height - input_height - palette_height,
        'palette_y': term.height - palette_height,
        'palette_height': palette_height,
    }
