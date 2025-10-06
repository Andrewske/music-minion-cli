"""Metadata editor command handlers."""

from dataclasses import replace
from music_minion.context import AppContext
from music_minion.ui.blessed.state import (
    UIState,
    add_history_line,
    set_feedback,
    show_metadata_editor,
    hide_metadata_editor,
    move_editor_selection,
    set_editor_mode,
    add_editor_change,
)


def handle_show_metadata_editor(ctx: AppContext, ui_state: UIState, track_id: int) -> tuple[AppContext, UIState]:
    """
    Handle showing metadata editor for a track.

    Args:
        ctx: Application context
        ui_state: Current UI state
        track_id: ID of track to edit

    Returns:
        Tuple of (updated AppContext, updated UIState)
    """
    from music_minion.core import database

    # Load all track metadata
    track = database.get_track_by_id(track_id)
    if not track:
        ui_state = add_history_line(ui_state, f"❌ Track not found", 'red')
        return ctx, ui_state

    # Load ratings, notes, tags
    ratings = database.get_track_ratings(track_id)
    notes = database.get_track_notes(track_id)
    tags = database.get_track_tags(track_id, include_blacklisted=False)

    # Build track data dict
    track_data = {
        'id': track_id,
        'file_path': track.get('file_path'),
        'title': track.get('title'),
        'artist': track.get('artist'),
        'album': track.get('album'),
        'year': track.get('year'),
        'bpm': track.get('bpm'),
        'key': track.get('key_signature'),
        'genre': track.get('genre'),
        'ratings': ratings,
        'notes': notes,
        'tags': tags,
    }

    # Show metadata editor
    ui_state = show_metadata_editor(ui_state, track_data)

    return ctx, ui_state


def handle_metadata_editor_navigation(ui_state: UIState, direction: int) -> UIState:
    """
    Handle arrow key navigation in metadata editor.

    Args:
        ui_state: Current UI state
        direction: -1 for up, 1 for down

    Returns:
        Updated UIState
    """
    if ui_state.editor_mode == 'main':
        # Main editor has 10 fields (7 basic + 3 multi-value)
        max_items = 10
    else:
        # List editor - count items
        items = ui_state.editor_data.get('items', [])
        max_items = len(items)

    return move_editor_selection(ui_state, direction, max_items)


def handle_metadata_editor_enter(ctx: AppContext, ui_state: UIState) -> tuple[AppContext, UIState]:
    """
    Handle Enter key in metadata editor.

    Args:
        ctx: Application context
        ui_state: Current UI state

    Returns:
        Tuple of (updated AppContext, updated UIState)
    """
    if ui_state.editor_mode == 'main':
        # Main editor: Enter opens field for editing
        return _handle_edit_field(ctx, ui_state)
    else:
        # List editor: Not implemented (would edit item)
        return ctx, ui_state


def handle_metadata_editor_delete(ctx: AppContext, ui_state: UIState) -> tuple[AppContext, UIState]:
    """
    Handle delete key in list editor.

    Args:
        ctx: Application context
        ui_state: Current UI state

    Returns:
        Tuple of (updated AppContext, updated UIState)
    """
    if ui_state.editor_mode != 'main':
        # Only works in list editor
        return _handle_delete_item(ctx, ui_state)

    return ctx, ui_state


def handle_metadata_editor_add(ctx: AppContext, ui_state: UIState) -> tuple[AppContext, UIState]:
    """
    Handle add key ('a') in list editor.

    Args:
        ctx: Application context
        ui_state: Current UI state

    Returns:
        Tuple of (updated AppContext, updated UIState)
    """
    if ui_state.editor_mode != 'main':
        # Only works in list editor
        return _handle_add_item(ctx, ui_state)

    return ctx, ui_state


def handle_metadata_editor_back(ui_state: UIState) -> UIState:
    """
    Handle back key ('q') in list editor - return to main editor.

    Args:
        ui_state: Current UI state

    Returns:
        Updated UIState
    """
    if ui_state.editor_mode != 'main':
        # Return to main editor
        return set_editor_mode(ui_state, 'main')

    return ui_state


def handle_metadata_editor_save(ctx: AppContext, ui_state: UIState) -> tuple[AppContext, UIState]:
    """
    Handle save and close (Esc key) - save all pending changes and close editor.

    Args:
        ctx: Application context
        ui_state: Current UI state

    Returns:
        Tuple of (updated AppContext, updated UIState)
    """
    if not ui_state.editor_changes:
        # No changes, just close
        ui_state = hide_metadata_editor(ui_state)
        return ctx, ui_state

    # Save all pending changes
    track_id = ui_state.editor_data.get('id')
    if not track_id:
        ui_state = hide_metadata_editor(ui_state)
        ui_state = add_history_line(ui_state, f"❌ Error: No track ID", 'red')
        return ctx, ui_state

    success = _save_all_changes(track_id, ui_state.editor_changes)

    if success:
        ui_state = hide_metadata_editor(ui_state)
        ui_state = add_history_line(ui_state, f"✅ Metadata saved", 'green')
        ui_state = set_feedback(ui_state, "Metadata saved", "✓")
    else:
        ui_state = add_history_line(ui_state, f"❌ Failed to save metadata", 'red')

    return ctx, ui_state


# Private helper functions

def _handle_edit_field(ctx: AppContext, ui_state: UIState) -> tuple[AppContext, UIState]:
    """Handle editing a field in main editor."""
    selected = ui_state.editor_selected
    track_data = ui_state.editor_data

    # Field list (same order as in metadata_editor.py)
    field_names = ['title', 'artist', 'album', 'year', 'bpm', 'key', 'genre', 'ratings', 'notes', 'tags']

    if selected >= len(field_names):
        return ctx, ui_state

    field_name = field_names[selected]

    # Check if multi-value field
    if field_name in ['ratings', 'notes', 'tags']:
        # Open list editor
        items = track_data.get(field_name, [])
        ui_state = set_editor_mode(ui_state, 'list_editor', {
            'editing_field': field_name,
            'items': items
        })
    else:
        # Single-value field: Would open text input (not implemented yet)
        # For now, show message
        ui_state = add_history_line(ui_state, f"⚠️  Editing {field_name} not yet implemented", 'yellow')

    return ctx, ui_state


def _handle_delete_item(ctx: AppContext, ui_state: UIState) -> tuple[AppContext, UIState]:
    """Handle deleting an item in list editor."""
    selected = ui_state.editor_selected
    editor_data = ui_state.editor_data
    field_type = editor_data.get('editing_field', '')
    items = editor_data.get('items', [])

    if selected >= len(items):
        return ctx, ui_state

    selected_item = items[selected]

    # Add to pending changes
    change_type = f'delete_{field_type[:-1]}'  # ratings -> delete_rating
    timestamp = selected_item.get('timestamp', '')

    ui_state = add_editor_change(ui_state, change_type, {'timestamp': timestamp})

    # Remove from display list
    new_items = items[:selected] + items[selected + 1:]
    ui_state = set_editor_mode(ui_state, 'list_editor', {
        'editing_field': field_type,
        'items': new_items
    })

    ui_state = add_history_line(ui_state, f"⚠️  Marked {field_type[:-1]} for deletion", 'yellow')

    return ctx, ui_state


def _handle_add_item(ctx: AppContext, ui_state: UIState) -> tuple[AppContext, UIState]:
    """Handle adding an item in list editor."""
    # Not implemented yet - would open input dialog
    ui_state = add_history_line(ui_state, f"⚠️  Adding items not yet implemented", 'yellow')
    return ctx, ui_state


def _save_all_changes(track_id: int, changes: dict) -> bool:
    """
    Save all pending changes to database.

    Args:
        track_id: Track ID
        changes: Dictionary of pending changes

    Returns:
        True if all changes saved successfully
    """
    from music_minion.core import database

    try:
        # 1. Save basic metadata changes
        basic = changes.get('basic', {})
        if basic:
            database.update_track_metadata(track_id, **basic)

        # 2. Delete ratings
        delete_ratings = changes.get('delete_rating', [])
        for item in delete_ratings:
            database.delete_rating(track_id, item['timestamp'])

        # 3. Update ratings
        update_ratings = changes.get('update_rating', [])
        for item in update_ratings:
            database.update_rating(track_id, item['old_timestamp'], item['new_type'])

        # 4. Add ratings
        add_ratings = changes.get('add_rating', [])
        for item in add_ratings:
            database.add_rating(track_id, item['rating_type'], item.get('context'))

        # 5. Delete notes
        delete_notes = changes.get('delete_note', [])
        for item in delete_notes:
            database.delete_note(track_id, item['timestamp'])

        # 6. Update notes
        update_notes = changes.get('update_note', [])
        for item in update_notes:
            database.update_note(track_id, item['old_timestamp'], item['new_text'])

        # 7. Add notes
        add_notes = changes.get('add_note', [])
        for item in add_notes:
            database.add_note(track_id, item['note_text'])

        # 8. Delete tags
        delete_tags = changes.get('delete_tag', [])
        for item in delete_tags:
            database.remove_tag(track_id, item['tag_name'])

        # 9. Add tags
        add_tags = changes.get('add_tag', [])
        for item in add_tags:
            database.add_tags(track_id, [item['tag_name']], source='user')

        return True

    except Exception as e:
        print(f"❌ Error saving metadata: {e}")
        return False
