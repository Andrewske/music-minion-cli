"""Terminal output utilities that prevent rendering artifacts."""

import sys

from blessed import Terminal


def write_at(
    term: Terminal, x: int, y: int, content: str, *, clear: bool = True
) -> None:
    """Write content at position, clearing the rest of the line by default.

    This utility prevents text overlap artifacts when new content is shorter
    than previous content at the same position.

    Args:
        term: Blessed terminal instance
        x: Column position (0-indexed)
        y: Row position (0-indexed)
        content: Text to write (can include terminal formatting)
        clear: Whether to clear to end of line (default True). Set to False
               only when intentionally appending to existing content.
    """
    if clear:
        sys.stdout.write(term.move_xy(x, y) + term.clear_eol + content)
    else:
        sys.stdout.write(term.move_xy(x, y) + content)
