from blessed import Terminal

from ..helpers import write_at
from ..state import UIState


EXPORT_FORMATS = [
    ("m3u8", "M3U8", "Standard playlist format"),
    ("crate", "Crate", "Serato DJ crate format"),
    ("csv", "CSV", "CSV with metadata"),
    ("all", "All", "Export all formats"),
]


def render_export_selector(term: Terminal, state: UIState, y: int, height: int) -> None:
    """
    Render export selector full screen for playlist.

    Args:
        term: blessed Terminal instance
        state: Current UI state
        y: Starting y position
        height: Available height for selector
    """
    if not state.export_selector_active or height <= 0 or y < 0:
        return

    try:
        selected_index = state.export_selector_selected
        playlist_name = state.export_selector_playlist_name

        # Reserve lines for header and footer
        header_lines = 3  # Title + playlist name + blank line
        footer_lines = 2  # Instructions + keyboard hints
        content_height = height - header_lines - footer_lines

        line_num = 0

        # Header
        if line_num < height:
            title = "Export Playlist"
            write_at(term, 0, y + line_num, title)
            line_num += 1

        if line_num < height:
            playlist_display = f"Playlist: {playlist_name}"
            write_at(term, 0, y + line_num, playlist_display)
            line_num += 1

        if line_num < height:
            write_at(term, 0, y + line_num, "")  # Blank line
            line_num += 1

        # Render export format options
        for i, (format_code, format_name, description) in enumerate(EXPORT_FORMATS):
            if line_num >= height - footer_lines:
                break

            # Selection indicator and format display
            if i == selected_index:
                format_text = f"[ {format_name} ]"
                desc_text = f" - {description} (selected)"
            else:
                format_text = f"  {format_name}  "
                desc_text = f" - {description}"
            full_text = format_text + desc_text

            # Truncate to terminal width to prevent wrapping issues
            try:
                max_width = term.width - 1  # Leave 1 char margin
            except Exception:
                max_width = 79  # Safe fallback
            if len(full_text) > max_width:
                full_text = full_text[: max_width - 3] + "..."

            write_at(term, 0, y + line_num, full_text)
            line_num += 1

        # Add spacing
        while line_num < height - footer_lines:
            write_at(term, 0, y + line_num, "")
            line_num += 1

        # Footer with instructions
        if line_num < height:
            instructions = "Select export format:"
            write_at(term, 0, y + line_num, instructions)
            line_num += 1

        if line_num < height:
            hints = "↑/↓ Navigate • Enter Export • q/Escape Cancel"
            write_at(term, 0, y + line_num, hints)
    except Exception as e:
        # Fallback rendering on error
        try:
            write_at(term, 0, y, f"Export selector error: {str(e)[:50]}", clear=True)
            y += 1
            write_at(
                term,
                0,
                y,
                "Export selector: Use arrow keys to select format",
                clear=True,
            )
        except Exception:
            pass  # If even fallback fails, do nothing
