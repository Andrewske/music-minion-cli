"""Metadata editor rendering for editing track metadata."""

import sys
from blessed import Terminal
from ..state import UIState

# Layout constants
EDITOR_HEADER_LINES = 3  # Title + track info + separator
EDITOR_FOOTER_LINES = 1  # Help text


def count_pending_changes(editor_changes: dict) -> int:
    """
    Count total number of pending changes.

    Args:
        editor_changes: Dictionary of pending changes

    Returns:
        Total number of changes (not just number of change types)
    """
    if not editor_changes:
        return 0

    count = 0

    # Count basic metadata changes (single dict)
    if 'basic' in editor_changes:
        # Count each changed field
        count += len(editor_changes['basic'])

    # Count list-based changes (deletions, additions, updates)
    for change_type, changes in editor_changes.items():
        if change_type != 'basic' and isinstance(changes, list):
            count += len(changes)

    return count


def render_metadata_editor(term: Terminal, state: UIState, y: int, height: int) -> None:
    """
    Render metadata editor - routes to main, list, or field editor based on mode.

    Args:
        term: blessed Terminal instance
        state: Current UI state
        y: Starting y position
        height: Available height for editor
    """
    if not state.editor_visible or height <= 0:
        return

    if state.editor_mode == 'main':
        render_main_editor(term, state, y, height)
    elif state.editor_mode == 'list_editor':
        render_list_editor(term, state, y, height)
    elif state.editor_mode == 'editing_field':
        render_field_editor(term, state, y, height)
    elif state.editor_mode == 'adding_item':
        render_add_item_editor(term, state, y, height)
    else:
        # Fallback for unknown modes
        render_main_editor(term, state, y, height)


def render_main_editor(term: Terminal, state: UIState, y: int, height: int) -> None:
    """
    Render main metadata editor with all fields.

    Shows:
    - Basic metadata: title, artist, album, year, bpm, key, genre
    - Multi-value: ratings (count), notes (count), tags (count)

    Args:
        term: blessed Terminal instance
        state: Current UI state
        y: Starting y position
        height: Available height for editor
    """
    track_data = state.editor_data
    selected_index = state.editor_selected

    # Build field list
    fields = _build_field_list(track_data)

    line_num = 0

    # Header - Track title
    if line_num < height:
        artist = track_data.get('artist', 'Unknown')
        title = track_data.get('title', 'Unknown')
        header_text = f"   🔧 Metadata: {artist} - {title}"
        sys.stdout.write(term.move_xy(0, y + line_num) + term.bold_cyan(header_text))
        line_num += 1

    # Metadata line - pending changes indicator
    if line_num < height:
        changes_count = count_pending_changes(state.editor_changes)
        if changes_count > 0:
            metadata_text = f"   ⚠️  {changes_count} pending change(s)"
            sys.stdout.write(term.move_xy(0, y + line_num) + term.yellow(metadata_text))
        else:
            metadata_text = "   No pending changes"
            sys.stdout.write(term.move_xy(0, y + line_num) + term.white(metadata_text))
        line_num += 1

    # Separator
    if line_num < height:
        sys.stdout.write(term.move_xy(0, y + line_num) + term.white("   " + "─" * 60))
        line_num += 1

    # Calculate content area
    content_height = height - EDITOR_HEADER_LINES - EDITOR_FOOTER_LINES

    # Render fields
    items_rendered = 0
    for field_index, (label, value, is_multi) in enumerate(fields):
        if items_rendered >= content_height:
            break

        if line_num >= height - EDITOR_FOOTER_LINES:
            break

        is_selected = field_index == selected_index

        # Format field line
        if is_multi:
            # Multi-value field: show count and arrow
            count = len(value) if value else 0
            field_text = f"{label:<15} {count} items ›"
        else:
            # Single-value field: show value
            display_value = value if value else "(empty)"
            field_text = f"{label:<15} {display_value}"

        if is_selected:
            # Selected field: highlighted background
            item_line = term.black_on_cyan(f"  {field_text[:70]}")
        else:
            # Normal field
            item_line = term.white(f"  {field_text[:70]}")

        sys.stdout.write(term.move_xy(0, y + line_num) + item_line)
        line_num += 1
        items_rendered += 1

    # Clear remaining lines
    while line_num < height - EDITOR_FOOTER_LINES:
        sys.stdout.write(term.move_xy(0, y + line_num) + term.clear_eol)
        line_num += 1

    # Footer help text
    if line_num < height:
        footer = "   ↑↓ navigate  Enter edit  Esc save & close"
        sys.stdout.write(term.move_xy(0, y + line_num) + term.white(footer))


def render_list_editor(term: Terminal, state: UIState, y: int, height: int) -> None:
    """
    Render generic list editor for multi-value fields (ratings, notes, tags).

    Args:
        term: blessed Terminal instance
        state: Current UI state
        y: Starting y position
        height: Available height for editor
    """
    editor_data = state.editor_data
    field_type = editor_data.get('editing_field', 'unknown')
    items = editor_data.get('items', [])
    selected_index = state.editor_selected

    # Bounds check: ensure selection is valid (defensive programming)
    if items and selected_index >= len(items):
        selected_index = len(items) - 1
    elif not items:
        selected_index = 0

    line_num = 0

    # Header - Field name
    if line_num < height:
        header_text = f"   📝 Edit {field_type.capitalize()}"
        sys.stdout.write(term.move_xy(0, y + line_num) + term.bold_cyan(header_text))
        line_num += 1

    # Count line
    if line_num < height:
        count_text = f"   {len(items)} item(s)"
        sys.stdout.write(term.move_xy(0, y + line_num) + term.white(count_text))
        line_num += 1

    # Separator
    if line_num < height:
        sys.stdout.write(term.move_xy(0, y + line_num) + term.white("   " + "─" * 60))
        line_num += 1

    # Calculate content area
    content_height = height - EDITOR_HEADER_LINES - EDITOR_FOOTER_LINES

    # Render items
    if not items:
        if line_num < height:
            empty_msg = "  No items"
            sys.stdout.write(term.move_xy(0, y + line_num) + term.white(empty_msg))
            line_num += 1
    else:
        items_rendered = 0
        for item_index, item in enumerate(items):
            if items_rendered >= content_height:
                break

            if line_num >= height - EDITOR_FOOTER_LINES:
                break

            is_selected = item_index == selected_index

            # Format item based on field type
            item_text = _format_list_item(field_type, item)

            if is_selected:
                # Selected item: highlighted background
                item_line = term.black_on_cyan(f"  {item_text[:70]}")
            else:
                # Normal item
                item_line = term.white(f"  {item_text[:70]}")

            sys.stdout.write(term.move_xy(0, y + line_num) + item_line)
            line_num += 1
            items_rendered += 1

    # Clear remaining lines
    while line_num < height - EDITOR_FOOTER_LINES:
        sys.stdout.write(term.move_xy(0, y + line_num) + term.clear_eol)
        line_num += 1

    # Footer help text
    if line_num < height:
        footer = "   ↑↓ navigate  d delete  a add  q back"
        sys.stdout.write(term.move_xy(0, y + line_num) + term.white(footer))


def render_field_editor(term: Terminal, state: UIState, y: int, height: int) -> None:
    """
    Render field editing mode for single-value fields.

    Args:
        term: blessed Terminal instance
        state: Current UI state
        y: Starting y position
        height: Available height for editor
    """
    editor_data = state.editor_data
    field_name = editor_data.get('editing_field_name', 'unknown')
    input_text = state.editor_input

    # Field labels for display
    field_labels = {
        'title': 'Title',
        'artist': 'Artist',
        'album': 'Album',
        'year': 'Year',
        'bpm': 'BPM',
        'key': 'Key Signature',
        'genre': 'Genre'
    }
    field_label = field_labels.get(field_name, field_name.capitalize())

    line_num = 0

    # Header
    if line_num < height:
        header_text = f"   ✏️  Edit {field_label}"
        sys.stdout.write(term.move_xy(0, y + line_num) + term.bold_cyan(header_text))
        line_num += 1

    # Hint line
    if line_num < height:
        hint_text = "   Type new value and press Enter to save, Esc to cancel"
        sys.stdout.write(term.move_xy(0, y + line_num) + term.white(hint_text))
        line_num += 1

    # Separator
    if line_num < height:
        sys.stdout.write(term.move_xy(0, y + line_num) + term.white("   " + "─" * 60))
        line_num += 1

    # Input field
    if line_num < height:
        # Show input with cursor
        input_display = f"   {field_label}: {input_text}█"
        sys.stdout.write(term.move_xy(0, y + line_num) + term.white(input_display))
        line_num += 1

    # Clear remaining lines
    while line_num < height:
        sys.stdout.write(term.move_xy(0, y + line_num) + term.clear_eol)
        line_num += 1


def render_add_item_editor(term: Terminal, state: UIState, y: int, height: int) -> None:
    """
    Render add item mode for adding new notes or tags.

    Args:
        term: blessed Terminal instance
        state: Current UI state
        y: Starting y position
        height: Available height for editor
    """
    editor_data = state.editor_data
    item_type = editor_data.get('adding_item_type', 'unknown')
    input_text = state.editor_input

    # Item type labels for display
    type_labels = {
        'notes': 'Note',
        'tags': 'Tag'
    }
    type_label = type_labels.get(item_type, item_type.capitalize())

    line_num = 0

    # Header
    if line_num < height:
        header_text = f"   ➕ Add New {type_label}"
        sys.stdout.write(term.move_xy(0, y + line_num) + term.bold_cyan(header_text))
        line_num += 1

    # Hint line
    if line_num < height:
        hint_text = "   Type text and press Enter to add, Esc to cancel"
        sys.stdout.write(term.move_xy(0, y + line_num) + term.white(hint_text))
        line_num += 1

    # Separator
    if line_num < height:
        sys.stdout.write(term.move_xy(0, y + line_num) + term.white("   " + "─" * 60))
        line_num += 1

    # Input field
    if line_num < height:
        # Show input with cursor
        input_display = f"   {type_label}: {input_text}█"
        sys.stdout.write(term.move_xy(0, y + line_num) + term.white(input_display))
        line_num += 1

    # Clear remaining lines
    while line_num < height:
        sys.stdout.write(term.move_xy(0, y + line_num) + term.clear_eol)
        line_num += 1


def _build_field_list(track_data: dict) -> list[tuple[str, any, bool]]:
    """
    Build list of metadata fields for display.

    Args:
        track_data: Track data dictionary

    Returns:
        List of (label, value, is_multi_value) tuples
    """
    fields = []

    # Basic single-value fields
    fields.append(("Title", track_data.get('title'), False))
    fields.append(("Artist", track_data.get('artist'), False))
    fields.append(("Album", track_data.get('album'), False))
    fields.append(("Year", track_data.get('year'), False))
    fields.append(("BPM", track_data.get('bpm'), False))
    fields.append(("Key", track_data.get('key'), False))
    fields.append(("Genre", track_data.get('genre'), False))

    # Multi-value fields (show count)
    fields.append(("Ratings", track_data.get('ratings', []), True))
    fields.append(("Notes", track_data.get('notes', []), True))
    fields.append(("Tags", track_data.get('tags', []), True))

    return fields


def _format_list_item(field_type: str, item: dict) -> str:
    """
    Format list item for display based on field type.

    Args:
        field_type: Type of field ('ratings', 'notes', 'tags')
        item: Item dictionary

    Returns:
        Formatted string for display
    """
    if field_type == 'ratings':
        rating_type = item.get('rating_type', 'unknown')
        timestamp = item.get('timestamp', '')[:16]  # Truncate timestamp
        return f"{rating_type:<10} {timestamp}"

    elif field_type == 'notes':
        note_text = item.get('note_text', '')
        timestamp = item.get('timestamp', '')[:16]
        # Truncate note text if too long
        note_preview = note_text[:40] + "..." if len(note_text) > 40 else note_text
        return f"{timestamp} {note_preview}"

    elif field_type == 'tags':
        tag_name = item.get('tag_name', '')
        source = item.get('source', 'user')
        return f"{tag_name:<20} [{source}]"

    else:
        return str(item)
