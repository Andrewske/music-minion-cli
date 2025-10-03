"""Playlist-related command handlers."""

from music_minion.context import AppContext
from music_minion.ui.blessed.state import (
    UIState,
    add_history_line,
    set_feedback,
    show_playlist_palette,
)
from music_minion.ui.blessed.components.palette import load_playlist_items


def handle_playlist_selection(ctx: AppContext, ui_state: UIState, playlist_name: str) -> tuple[AppContext, UIState]:
    """
    Handle playlist selection from palette.

    Args:
        ctx: Application context
        ui_state: Current UI state
        playlist_name: Name of playlist to select

    Returns:
        Tuple of (updated AppContext, updated UIState)
    """
    from music_minion.domain import playlists

    # Get playlist by name
    pl = playlists.get_playlist_by_name(playlist_name)
    if not pl:
        ui_state = add_history_line(ui_state, f"❌ Playlist '{playlist_name}' not found", 'red')
        return ctx, ui_state

    # Call playlist active command
    from music_minion.commands.playlist import handle_playlist_active_command

    # Update context with active playlist
    ctx, _ = handle_playlist_active_command(ctx, [playlist_name])

    # Add success message
    ui_state = add_history_line(ui_state, f"✅ Activated playlist: {playlist_name}", 'green')
    ui_state = set_feedback(ui_state, f"✓ {playlist_name}", "✓")

    return ctx, ui_state


def handle_playlist_deletion(ctx: AppContext, ui_state: UIState, playlist_name: str) -> tuple[AppContext, UIState]:
    """
    Handle playlist deletion from palette.

    Args:
        ctx: Application context
        ui_state: Current UI state
        playlist_name: Name of playlist to delete

    Returns:
        Tuple of (updated AppContext, updated UIState)
    """
    from music_minion.domain import playlists

    # Get playlist by name
    pl = playlists.get_playlist_by_name(playlist_name)
    if not pl:
        ui_state = add_history_line(ui_state, f"❌ Playlist '{playlist_name}' not found", 'red')
        return ctx, ui_state

    # Check if it's the active playlist
    is_active = ctx.active_playlist_id == pl['id']

    # Delete the playlist
    try:
        playlists.delete_playlist(pl['id'])

        # Clear active playlist if it was deleted
        if is_active:
            ctx = ctx.with_active_playlist(None)

        ui_state = add_history_line(ui_state, f"✅ Deleted playlist: {playlist_name}", 'green')
        ui_state = set_feedback(ui_state, f"✓ Deleted", "✓")

        # Refresh playlist palette if visible
        if ui_state.palette_visible and ui_state.palette_mode == 'playlist':
            items = load_playlist_items(ctx)
            ui_state = show_playlist_palette(ui_state, items)

    except (ValueError, KeyError, TypeError) as e:
        ui_state = add_history_line(ui_state, f"❌ Failed to delete playlist: {e}", 'red')
    except OSError as e:
        ui_state = add_history_line(ui_state, f"❌ Database error: {e}", 'red')

    return ctx, ui_state
