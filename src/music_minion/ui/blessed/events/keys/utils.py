"""Shared keyboard utility functions."""

from blessed.keyboard import Keystroke


def parse_key(key: Keystroke) -> dict:
    """
    Parse keystroke into event dictionary.

    Args:
        key: blessed Keystroke

    Returns:
        Event dictionary describing the key press
    """
    event = {
        "type": "unknown",
        "key": key,
        "name": key.name if hasattr(key, "name") else None,
        "char": str(key) if key and key.isprintable() else None,
    }

    # Identify key type
    if key.name == "KEY_ENTER":
        event["type"] = "enter"
    elif key.name == "KEY_ESCAPE":
        event["type"] = "escape"
    elif key.name == "KEY_BACKSPACE" or key == "\x7f":
        event["type"] = "backspace"
    elif key.name == "KEY_DELETE" or str(key) == "\x1b[3~":
        event["type"] = "delete"
    elif key.name == "KEY_UP":
        event["type"] = "arrow_up"
    elif key.name == "KEY_DOWN":
        event["type"] = "arrow_down"
    elif key.name == "KEY_LEFT":
        event["type"] = "arrow_left"
    elif key.name == "KEY_RIGHT":
        event["type"] = "arrow_right"
    elif key.name == "KEY_SLEFT":  # Shift+Left
        event["type"] = "shift_arrow_left"
    elif key.name == "KEY_SRIGHT":  # Shift+Right
        event["type"] = "shift_arrow_right"
    elif key.name == "KEY_PGUP":  # Page Up (blessed uses PGUP not PPAGE)
        event["type"] = "page_up"
    elif key.name == "KEY_PGDOWN":  # Page Down (blessed uses PGDOWN not NPAGE)
        event["type"] = "page_down"
    elif key.name == "KEY_HOME":
        event["type"] = "home"
    elif key.name == "KEY_END":
        event["type"] = "end"
    elif key == "\x03":  # Ctrl+C
        event["type"] = "ctrl_c"
    elif key == "\x0c":  # Ctrl+L
        event["type"] = "ctrl_l"
    elif key == "\x15":  # Ctrl+U (half page up - vim style)
        event["type"] = "page_up"
    elif key == "\x04":  # Ctrl+D (half page down - vim style)
        event["type"] = "page_down"
    elif key and key.isprintable():
        event["type"] = "char"

    return event
