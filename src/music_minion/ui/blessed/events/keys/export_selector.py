from dataclasses import replace
from music_minion.ui.blessed.state import UIState, exit_export_selector
from music_minion.ui.blessed.components.export_selector import EXPORT_FORMATS


def handle_export_selector_key(
    state: UIState, event: dict
) -> tuple[UIState, str | None]:
    """
    Handle keyboard events for export selector full screen mode.

    Args:
        state: Current UI state (export selector must be active)
        event: Parsed key event

    Returns:
        Tuple of (updated state, command to execute or None)
    """
    try:
        # Escape or 'q' exits selector
        if event["type"] == "escape" or (
            event["type"] == "char" and event["char"] == "q"
        ):
            return exit_export_selector(state), None

        # Arrow key navigation (try multiple possible key codes)
        if event["type"] in ("arrow_up", "key_up") or (
            event["type"] == "char" and event["char"] == "k"
        ):
            new_selected = (state.export_selector_selected - 1) % len(EXPORT_FORMATS)
            return replace(state, export_selector_selected=new_selected), None

        if event["type"] in ("arrow_down", "key_down") or (
            event["type"] == "char" and event["char"] == "j"
        ):
            new_selected = (state.export_selector_selected + 1) % len(EXPORT_FORMATS)
            return replace(state, export_selector_selected=new_selected), None

        # Enter executes export
        if event["type"] == "enter":
            selected_format = EXPORT_FORMATS[state.export_selector_selected][
                0
            ]  # Get format code
            playlist_id = state.export_selector_playlist_id
            playlist_name = state.export_selector_playlist_name

            if playlist_id is not None:
                from urllib.parse import quote

                encoded_name = quote(str(playlist_name))
                command = f"__EXPORT_PLAYLIST__:{playlist_id}|{encoded_name}|{selected_format}"
                return exit_export_selector(state), command

        # Any other key: stay in same state
        return state, None
    except Exception:
        # On any error, exit selector to prevent UI failure
        return exit_export_selector(state), None
