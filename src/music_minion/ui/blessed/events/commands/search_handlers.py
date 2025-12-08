"""Action handlers for track search feature."""

from dataclasses import replace
from music_minion.context import AppContext
from music_minion.ui.blessed.state import (
    UIState,
    hide_palette,
    show_playlist_palette,
    show_metadata_editor,
    add_history_line,
)
from music_minion.core import database
from music_minion.domain.playlists import crud as playlists


def handle_search_play_track(
    ctx: AppContext, ui_state: UIState, track_id: int
) -> tuple[AppContext, UIState]:
    """
    Execute 'Play Track' action from search.

    Args:
        ctx: Current application context
        ui_state: Current UI state
        track_id: ID of track to play

    Returns:
        Updated context and state
    """
    # Get track from database
    track = database.get_track_by_id(track_id)
    if not track:
        ui_state = add_history_line(ui_state, "❌ Track not found", "red")
        ui_state = hide_palette(ui_state)
        return ctx, ui_state

    # Close search
    ui_state = hide_palette(ui_state)

    # Start MPV if not running
    from music_minion.domain.playback.player import play_file, is_mpv_running, start_mpv

    if not is_mpv_running(ctx.player_state):
        new_state = start_mpv(ctx.config)
        if not new_state:
            ui_state = add_history_line(
                ui_state, "❌ Failed to start music player", "red"
            )
            return ctx, ui_state
        ctx = ctx.with_player_state(new_state)

    # Send play command to player
    try:
        ctx.player_state, success = play_file(
            ctx.player_state, track["local_path"], track["id"]
        )
        if success:
            ui_state = add_history_line(
                ui_state,
                f"▶ Playing: {track.get('artist', 'Unknown')} - {track.get('title', 'Unknown')}",
                "green",
            )
        else:
            ui_state = add_history_line(ui_state, f"❌ Failed to play track", "red")
    except Exception as e:
        ui_state = add_history_line(ui_state, f"❌ Error playing track: {e}", "red")

    return ctx, ui_state


def handle_search_add_to_playlist(
    ctx: AppContext, ui_state: UIState, track_id: int
) -> tuple[AppContext, UIState]:
    """
    Execute 'Add to Playlist' action from search.

    Opens playlist palette for selection, then adds track.

    Args:
        ctx: Current application context
        ui_state: Current UI state
        track_id: ID of track to add

    Returns:
        Updated context and state
    """
    # Get all playlists
    all_playlists = playlists.get_playlists_sorted_by_recent()
    manual_playlists = [p for p in all_playlists if p["type"] == "manual"]

    if not manual_playlists:
        ui_state = add_history_line(
            ui_state,
            "❌ No manual playlists available. Create one first with 'playlist new manual <name>'",
            "red",
        )
        ui_state = hide_palette(ui_state)
        return ctx, ui_state

    # Close search and open playlist palette
    ui_state = hide_palette(ui_state)

    # Build playlist items for palette
    playlist_items = []
    for playlist in manual_playlists:
        name = playlist["name"]
        track_count = playlist.get("track_count", 0)
        desc = f"{track_count} tracks"
        playlist_items.append(("Playlists", name, "📝", desc))

    # Store track_id in a way the palette handler can access it
    # We'll use the palette mode to indicate this is an "add track" operation
    ui_state = show_playlist_palette(ui_state, playlist_items)

    # Store track_id in confirmation data (reusing this field for context)
    ui_state = replace(ui_state, confirmation_data={"pending_add_track_id": track_id})

    return ctx, ui_state


def handle_search_edit_metadata(
    ctx: AppContext, ui_state: UIState, track_id: int
) -> tuple[AppContext, UIState]:
    """
    Execute 'Edit Metadata' action from search.

    Opens metadata editor with track data.

    Args:
        ctx: Current application context
        ui_state: Current UI state
        track_id: ID of track to edit

    Returns:
        Updated context and state
    """
    # Get track with full metadata
    track = database.get_track_by_id(track_id)
    if not track:
        ui_state = add_history_line(ui_state, "❌ Track not found", "red")
        ui_state = hide_palette(ui_state)
        return ctx, ui_state

    # Get tags, notes, ratings
    tags = database.get_track_tags(track_id)
    notes = database.get_track_notes(track_id)
    ratings = database.get_track_ratings(track_id)

    # Build editor data
    editor_data = {
        "id": track_id,
        "title": track.get("title", ""),
        "artist": track.get("artist", ""),
        "remix_artist": track.get("remix_artist", ""),
        "album": track.get("album", ""),
        "year": track.get("year", ""),
        "genre": track.get("genre", ""),
        "bpm": track.get("bpm", ""),
        "key_signature": track.get("key_signature", ""),
        "tags": tags,
        "notes": notes,
        "ratings": ratings,
        "local_path": track["local_path"],
    }

    # Close search and open editor
    ui_state = hide_palette(ui_state)
    ui_state = show_metadata_editor(ui_state, editor_data)

    return ctx, ui_state
