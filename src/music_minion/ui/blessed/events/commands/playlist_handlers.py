"""Playlist-related command handlers."""

from dataclasses import replace
from music_minion.context import AppContext
from music_minion.ui.blessed.state import (
    UIState,
    add_history_line,
    set_feedback,
    show_playlist_palette,
)
from music_minion.ui.blessed.components.palette import load_playlist_items


def handle_playlist_selection(
    ctx: AppContext, ui_state: UIState, playlist_name: str
) -> tuple[AppContext, UIState]:
    """
    Handle playlist selection from palette.

    Can either:
    - Activate playlist for playback (default)
    - Add a pending track to playlist (when called from search "Add to Playlist")

    Args:
        ctx: Application context
        ui_state: Current UI state
        playlist_name: Name of playlist to select

    Returns:
        Tuple of (updated AppContext, updated UIState)
    """
    from music_minion.domain import playlists
    from music_minion.core import database
    from music_minion import helpers

    # Get playlist by name
    pl = playlists.get_playlist_by_name(playlist_name)
    if not pl:
        ui_state = add_history_line(
            ui_state, f"❌ Playlist '{playlist_name}' not found", "red"
        )
        return ctx, ui_state

    # Check if this is an "add track" operation from search
    pending_track_id = (
        ui_state.confirmation_data.get("pending_add_track_id")
        if ui_state.confirmation_data
        else None
    )

    if pending_track_id is not None:
        # Add track to playlist instead of activating
        try:
            if playlists.add_track_to_playlist(pl["id"], pending_track_id):
                # Get track info for display
                track = database.get_track_by_id(pending_track_id)
                if track:
                    display_name = f"{track.get('artist', 'Unknown')} - {track.get('title', 'Unknown')}"
                    ui_state = add_history_line(
                        ui_state,
                        f"✅ Added to '{playlist_name}': {display_name}",
                        "green",
                    )
                else:
                    ui_state = add_history_line(
                        ui_state,
                        f"✅ Added track to playlist: {playlist_name}",
                        "green",
                    )

                ui_state = set_feedback(ui_state, f"✓ Added to {playlist_name}", "✓")

                # Auto-export if enabled
                helpers.auto_export_if_enabled(pl["id"], ctx)
            else:
                ui_state = add_history_line(
                    ui_state,
                    f"Track is already in playlist '{playlist_name}'",
                    "yellow",
                )
        except ValueError as e:
            ui_state = add_history_line(ui_state, f"❌ Error: {e}", "red")
        except Exception as e:
            ui_state = add_history_line(
                ui_state, f"❌ Error adding track to playlist: {e}", "red"
            )

        # Clear confirmation data
        ui_state = replace(ui_state, confirmation_data=None)
    else:
        # Default behavior: activate playlist
        from music_minion.commands.playlist import handle_playlist_active_command

        # Update context with active playlist
        ctx, _ = handle_playlist_active_command(ctx, [playlist_name])

        # Add success message
        ui_state = add_history_line(
            ui_state, f"✅ Activated playlist: {playlist_name}", "green"
        )
        ui_state = set_feedback(ui_state, f"✓ {playlist_name}", "✓")

    return ctx, ui_state


def handle_playlist_deletion(
    ctx: AppContext, ui_state: UIState, playlist_name: str
) -> tuple[AppContext, UIState]:
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
        ui_state = add_history_line(
            ui_state, f"❌ Playlist '{playlist_name}' not found", "red"
        )
        return ctx, ui_state

    # Check if it's the active playlist
    is_active = ctx.active_playlist_id == pl["id"]

    # Delete the playlist
    try:
        playlists.delete_playlist(pl["id"])

        # Clear active playlist if it was deleted
        if is_active:
            ctx = ctx.with_active_playlist(None)

        ui_state = add_history_line(
            ui_state, f"✅ Deleted playlist: {playlist_name}", "green"
        )
        ui_state = set_feedback(ui_state, f"✓ Deleted", "✓")

        # Refresh playlist palette if visible
        if ui_state.palette_visible and ui_state.palette_mode == "playlist":
            items = load_playlist_items(ui_state.active_library)
            ui_state = show_playlist_palette(ui_state, items)

    except (ValueError, KeyError, TypeError) as e:
        ui_state = add_history_line(
            ui_state, f"❌ Failed to delete playlist: {e}", "red"
        )
    except OSError as e:
        ui_state = add_history_line(ui_state, f"❌ Database error: {e}", "red")

    return ctx, ui_state
