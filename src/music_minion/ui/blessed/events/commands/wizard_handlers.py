"""Wizard-related command handlers."""

import uuid
from music_minion.context import AppContext
from ..state import (
    UIState,
    add_history_line,
    set_feedback,
    cancel_wizard,
)


def handle_wizard_save(ctx: AppContext, ui_state: UIState) -> tuple[AppContext, UIState]:
    """
    Handle saving a smart playlist from wizard.

    Args:
        ctx: Application context
        ui_state: Current UI state

    Returns:
        Tuple of (updated AppContext, updated UIState)
    """
    from music_minion.domain import playlists

    if not ui_state.wizard_active or ui_state.wizard_type != 'smart_playlist':
        return ctx, ui_state

    wizard_data = ui_state.wizard_data

    # Get playlist name
    playlist_name = wizard_data.get('name', '').strip()
    if not playlist_name:
        ui_state = add_history_line(ui_state, "❌ Error: Playlist name is required", 'red')
        ui_state = cancel_wizard(ui_state)
        return ctx, ui_state

    # Get filters
    filters = wizard_data.get('filters', [])
    if not filters:
        ui_state = add_history_line(ui_state, "❌ Error: At least one filter is required", 'red')
        ui_state = cancel_wizard(ui_state)
        return ctx, ui_state

    # Generate unique ID
    playlist_id = str(uuid.uuid4())

    # Create smart playlist
    try:
        playlists.create_smart_playlist(
            playlist_id=playlist_id,
            name=playlist_name,
            description=wizard_data.get('description', ''),
            filters=filters
        )

        ui_state = add_history_line(ui_state, f"✅ Created smart playlist: {playlist_name}", 'green')
        ui_state = set_feedback(ui_state, f"✓ Created {playlist_name}", "✓")

    except ValueError as e:
        ui_state = add_history_line(ui_state, f"❌ Error: {e}", 'red')
    except (KeyError, TypeError, OSError) as e:
        ui_state = add_history_line(ui_state, f"❌ Error creating playlist: {e}", 'red')

    # Close wizard
    ui_state = cancel_wizard(ui_state)

    return ctx, ui_state
