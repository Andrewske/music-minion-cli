"""Smart Playlist Wizard rendering component."""

from blessed import Terminal

from ..helpers import write_at
from music_minion.ui.blessed.helpers.selection import render_selection_list
from ..state import UIState


def render_smart_playlist_wizard(
    term: Terminal, state: UIState, y: int, height: int
) -> None:
    """
    Render smart playlist wizard UI.

    Args:
        term: blessed Terminal instance
        state: Current UI state
        y: Starting y position
        height: Available height for wizard
    """
    if not state.wizard_active or state.wizard_type != "smart_playlist":
        return

    if height <= 0:
        return

    wizard_data = state.wizard_data
    playlist_name = wizard_data.get("name", "Unknown")
    filters_added = wizard_data.get("filters", [])
    current_step = state.wizard_step

    # Step titles and numbers
    steps = {
        "field": (1, "Select Field"),
        "operator": (2, "Select Operator"),
        "value": (3, "Enter Value"),
        "conjunction": (4, "Combine Filters"),
        "preview": (5, "Preview & Confirm"),
    }

    step_num, step_title = steps.get(current_step, (0, "Unknown"))
    total_steps = 5

    line_num = 0

    # Header with progress
    if line_num < height:
        header_text = f"   🧙 Smart Playlist Wizard: {playlist_name}"
        write_at(term, 0, y + line_num, term.bold_cyan(header_text))
        line_num += 1

    # Progress indicator
    if line_num < height:
        progress_text = f"   Step {step_num}/{total_steps}: {step_title}"
        write_at(term, 0, y + line_num, term.white(progress_text))
        line_num += 1

    # Separator
    if line_num < height:
        write_at(term, 0, y + line_num, term.white("   " + "─" * 60))
        line_num += 1

    # Show error message if validation failed
    if state.wizard_error and line_num < height:
        error_text = f"   ❌ {state.wizard_error}"
        write_at(term, 0, y + line_num, term.red(error_text))
        line_num += 1
        # Blank line after error
        if line_num < height:
            write_at(term, 0, y + line_num, "")
            line_num += 1

    # Show filters added so far
    if filters_added and line_num < height:
        write_at(term, 0, y + line_num, term.bold("   Filters added:"))
        line_num += 1

        for i, f in enumerate(filters_added, 1):
            if line_num >= height - 3:  # Leave room for footer
                break
            field = f.get("field", "")
            operator = f.get("operator", "")
            value = f.get("value", "")
            conjunction = f.get("conjunction", "AND")
            prefix = f"   {conjunction}" if i > 1 else "   "
            filter_text = f"{prefix} {field} {operator} '{value}'"
            write_at(term, 0, y + line_num, term.green(filter_text))
            line_num += 1

        # Blank line after filters
        if line_num < height:
            write_at(term, 0, y + line_num, "")
            line_num += 1

    # Step-specific content (each returns lines rendered)
    if current_step == "field":
        lines_rendered = _render_field_step(
            term, state, y + line_num, height - line_num
        )
        line_num += lines_rendered
    elif current_step == "operator":
        lines_rendered = _render_operator_step(
            term, state, y + line_num, height - line_num
        )
        line_num += lines_rendered
    elif current_step == "value":
        lines_rendered = _render_value_step(
            term, state, y + line_num, height - line_num
        )
        line_num += lines_rendered
    elif current_step == "conjunction":
        lines_rendered = _render_conjunction_step(
            term, state, y + line_num, height - line_num
        )
        line_num += lines_rendered
    elif current_step == "preview":
        lines_rendered = _render_preview_step(
            term, state, y + line_num, height - line_num
        )
        line_num += lines_rendered

    # Clear remaining lines
    while line_num < height:
        write_at(term, 0, y + line_num, "")
        line_num += 1


def _render_field_step(term: Terminal, state: UIState, y: int, height: int) -> int:
    """Render field selection step with arrow key selection."""
    return render_selection_list(
        term,
        state.wizard_options,
        state.wizard_selected,
        y,
        height,
        instruction="Select field (↑↓ arrows, Enter to choose):",
    )


def _render_operator_step(term: Terminal, state: UIState, y: int, height: int) -> int:
    """Render operator selection step with arrow key selection."""
    wizard_data = state.wizard_data
    field = wizard_data.get("current_field", "")
    instruction = f"Select operator for '{field}' (↑↓ arrows, Enter to choose):"

    return render_selection_list(
        term,
        state.wizard_options,
        state.wizard_selected,
        y,
        height,
        instruction=instruction,
    )


def _render_value_step(term: Terminal, state: UIState, y: int, height: int) -> int:
    """
    Render value entry step.

    Returns:
        Number of lines rendered
    """
    if height <= 0:
        return 0

    wizard_data = state.wizard_data
    field = wizard_data.get("current_field", "")
    operator = wizard_data.get("current_operator", "")

    line_num = 0

    # Instructions
    if line_num < height:
        instruction = f"   Enter value for: {field} {operator}"
        write_at(term, 0, y + line_num, term.white(instruction))
        line_num += 1

    # Show current input
    if line_num < height:
        current_value = state.input_text
        value_line = f"   Value: {current_value}_"
        write_at(term, 0, y + line_num, term.cyan(value_line))
        line_num += 1

    return line_num


def _render_conjunction_step(
    term: Terminal, state: UIState, y: int, height: int
) -> int:
    """
    Render conjunction selection step with arrow key selection.

    Returns:
        Number of lines rendered
    """
    if height <= 0:
        return 0

    line_num = 0

    # Instructions
    if line_num < height:
        write_at(
            term,
            0,
            y + line_num,
            term.white("   Combine with previous filter (↑↓ arrows, Enter to choose):"),
        )
        line_num += 1

    # Options with descriptions
    descriptions = {"AND": "All conditions must match", "OR": "Any condition can match"}

    # Render options with selection highlighting
    for i, option in enumerate(state.wizard_options):
        if line_num >= height:
            break

        desc = descriptions.get(option, "")

        # Highlight selected option
        if i == state.wizard_selected:
            prefix = "   ▶ "
            text = term.bold_green(f"{option} - {desc}")
        else:
            prefix = "     "
            text = term.white(f"{option} - {desc}")

        write_at(term, 0, y + line_num, prefix + text)
        line_num += 1

    return line_num


def _render_preview_step(term: Terminal, state: UIState, y: int, height: int) -> int:
    """
    Render preview and confirmation step.

    Returns:
        Number of lines rendered
    """
    if height <= 0:
        return 0

    wizard_data = state.wizard_data
    matching_count = wizard_data.get("matching_count", 0)
    preview_tracks = wizard_data.get("preview_tracks", [])

    line_num = 0

    # Matching count
    if line_num < height:
        count_line = f"   ✅ Found {matching_count} matching tracks"
        write_at(term, 0, y + line_num, term.green(count_line))
        line_num += 1

    # Blank line
    if line_num < height:
        write_at(term, 0, y + line_num, "")
        line_num += 1

    # Preview tracks
    if preview_tracks and line_num < height:
        write_at(term, 0, y + line_num, term.white("   Preview (first 5):"))
        line_num += 1

        for i, track in enumerate(preview_tracks[:5], 1):
            if line_num >= height:
                break
            artist = track.get("artist", "Unknown")
            title = track.get("title", "Unknown")
            track_line = f"     {i}. {artist} - {title}"
            write_at(term, 0, y + line_num, term.white(track_line))
            line_num += 1

    return line_num


def get_wizard_footer_text(state: UIState) -> str:
    """
    Get footer text for wizard based on current step.

    Args:
        state: Current UI state

    Returns:
        Footer help text
    """
    step = state.wizard_step

    # Steps with arrow key selection
    if step in ["field", "operator", "conjunction"]:
        return "   ↑↓ to select  •  Enter to choose  •  Esc to cancel"
    # Value step with text input
    elif step == "value":
        return "   Type value and press Enter  •  Esc to cancel"
    # Preview step
    elif step == "preview":
        return "   Enter to save  •  A to add another filter  •  Esc to cancel"
    else:
        return "   Esc to cancel"
