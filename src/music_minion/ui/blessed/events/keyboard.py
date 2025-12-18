"""Keyboard event handling dispatcher for all modes.

This module handles keyboard input routing to mode-specific handlers.
All mode logic has been extracted to focused modules in the keys/ directory.

Key Functions:
    - handle_key: Main keyboard dispatcher
"""

from blessed.keyboard import Keystroke
from music_minion.ui.blessed.state import UIState, InternalCommand
from .keys import (
    parse_key,
    handle_wizard_key,
    handle_track_viewer_key,
    handle_rating_history_key,
    handle_comparison_history_key,
    handle_analytics_viewer_key,
    handle_metadata_editor_key,
    handle_comparison_key,
    handle_export_selector_key,
    handle_normal_mode_key,
)


def detect_mode(state: UIState) -> str:
    """
    Detect the current active mode based on UI state.

    Returns mode name as a string for use in dispatch logic.
    Priority order matches the original if/elif chain.

    Args:
        state: Current UI state

    Returns:
        Mode name: "comparison", "wizard", "playlist_builder", "track_viewer",
                   "rating_history", "comparison_history", "analytics_viewer",
                   "metadata_editor", "export_options", or "normal"
    """
    if state.comparison.active:
        return "comparison"
    elif state.wizard_active:
        return "wizard"
    elif state.builder.active:
        return "playlist_builder"
    elif state.export_selector_active:
        return "export_selector"
    elif state.track_viewer_visible:
        return "track_viewer"
    elif state.rating_history_visible:
        return "rating_history"
    elif state.comparison_history_visible:
        return "comparison_history"
    elif state.analytics_viewer_visible:
        return "analytics_viewer"
    elif state.editor_visible:
        return "metadata_editor"
    else:
        return "normal"


def handle_key(
    state: UIState,
    key: Keystroke,
    palette_height: int = 10,
    analytics_viewer_height: int = 30,
) -> tuple[UIState, str | InternalCommand | None]:
    """
    Handle keyboard input and return updated state.

    Routes keyboard events to appropriate mode handlers using pattern matching.
    Priority order (highest to lowest):
    1. Confirmation dialogs (handled in normal mode)
    2. Comparison mode (allows fallthrough for seek controls)
    3. Wizard mode
    4. Track viewer mode
    5. Rating history viewer
    6. Comparison history viewer
    7. Analytics viewer
    8. Metadata editor
    9. Review mode (handled in normal mode)
    10. Normal mode (default)

    Args:
        state: Current UI state
        key: blessed Keystroke
        palette_height: Available height for palette (for scroll calculations)
        analytics_viewer_height: Available height for analytics viewer (for scroll calculations)

    Returns:
        Tuple of (updated state, command to execute or None)
    """
    event = parse_key(key)
    mode = detect_mode(state)

    # Comparison mode has special fallthrough behavior for seek controls
    if mode == "comparison":
        state_updated, cmd = handle_comparison_key(key, state)
        if state_updated is not None:
            return state_updated, cmd
        # Fall through to normal mode if comparison handler returned None
        mode = "normal"

    # Dispatch to mode-specific handlers
    match mode:
        case "wizard":
            return handle_wizard_key(state, event)
        case "playlist_builder":
            from music_minion.ui.blessed.events.keys.playlist_builder import (
                handle_playlist_builder_key,
            )

            return handle_playlist_builder_key(state, event, palette_height)
        case "export_selector":
            return handle_export_selector_key(state, event)
        case "track_viewer":
            return handle_track_viewer_key(state, event, palette_height)
        case "rating_history":
            return handle_rating_history_key(state, event, palette_height)
        case "comparison_history":
            return handle_comparison_history_key(state, event, palette_height)
        case "analytics_viewer":
            return handle_analytics_viewer_key(state, event, analytics_viewer_height)
        case "metadata_editor":
            return handle_metadata_editor_key(state, event)
        case _:
            # Normal mode (default) - handles confirmation dialogs, review mode, palette, search, etc.
            return handle_normal_mode_key(state, event, palette_height)
