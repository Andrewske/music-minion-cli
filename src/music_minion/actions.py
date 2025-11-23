"""Composite action handlers for Music Minion CLI.

Provides pre-defined multi-step actions for hotkey shortcuts and workflows.
Each action returns (AppContext, success, message) for detailed feedback.
"""

from datetime import datetime
from typing import Optional, Tuple

from loguru import logger

from music_minion.commands import playback, rating
from music_minion.context import AppContext
from music_minion.core import database
from music_minion.core.output import log
from music_minion.domain import library, playlists


def get_current_month_playlist() -> str:
    """
    Get the playlist name for the current month.

    Returns:
        Playlist name in format "{Month} {YY}" (e.g., "Nov 25", "Dec 25")
    """
    now = datetime.now()
    month = now.strftime("%b")  # "Nov", "Dec", etc.
    year = now.strftime("%y")  # "25", "26", etc.
    return f"{month} {year}"


def get_current_track_info(
    ctx: AppContext,
) -> Optional[Tuple[int, dict, library.Track]]:
    """
    Get current track information from context.

    Args:
        ctx: Application context

    Returns:
        (track_id, db_track, track_object) or None if no track playing
    """
    if not ctx.player_state.current_track:
        return None

    # Get track ID from player state
    track_id = ctx.player_state.current_track_id
    if not track_id:
        return None

    # Get full track info from database
    db_track = database.get_track_by_id(track_id)
    if not db_track:
        return None

    # Find Track object in memory for display (multi-source lookup)
    current_track = None
    for track in ctx.music_tracks:
        if (
            (track.local_path and track.local_path == db_track.get("local_path"))
            or (
                track.soundcloud_id
                and track.soundcloud_id == db_track.get("soundcloud_id")
            )
            or (track.spotify_id and track.spotify_id == db_track.get("spotify_id"))
            or (track.youtube_id and track.youtube_id == db_track.get("youtube_id"))
        ):
            current_track = track
            break

    if not current_track:
        return None

    return (track_id, db_track, current_track)


def ensure_playlist_exists(name: str) -> Optional[dict]:
    """
    Ensure a playlist exists, creating it if necessary.

    Args:
        name: Playlist name

    Returns:
        Playlist dict or None if creation failed
    """
    # Check if playlist exists
    playlist = playlists.get_playlist_by_name(name)
    if playlist:
        return playlist

    # Create manual playlist
    try:
        playlist_id = playlists.create_playlist(
            name, "manual", description=f"Auto-created playlist: {name}"
        )
        return playlists.get_playlist_by_id(playlist_id)
    except Exception:
        return None


def execute_like_and_add_dated(ctx: AppContext) -> Tuple[AppContext, bool, str]:
    """
    Like current track and add to current month's playlist.

    Args:
        ctx: Application context

    Returns:
        (updated_context, success, message)
    """
    # Get current track info
    track_info = get_current_track_info(ctx)
    if not track_info:
        return ctx, False, "❌ No track playing"

    track_id, db_track, current_track = track_info
    display_name = library.get_display_name(current_track)

    # Show immediate feedback
    log("⏳ Processing like and add to playlist...", level="info")

    # Capture month at action time (avoid month boundary race condition)
    playlist_name = get_current_month_playlist()

    # Remove from reposts playlist (if exists)
    try:
        reposts_playlist = playlists.get_playlist_by_name("reposts")
        if reposts_playlist:
            removed = playlists.remove_track_from_playlist(
                reposts_playlist["id"], track_id
            )
            if removed:
                logger.info(f"Removed track {track_id} from reposts playlist")
                log("   ✓ Removed from reposts", level="info")
    except Exception as e:
        logger.exception(f"Failed to remove track {track_id} from reposts playlist")
        log(f"   ⚠ Warning: Failed to remove from reposts: {str(e)}", level="warning")

    # Execute like command
    ctx, _ = rating.handle_like_command(ctx)
    like_success = True  # Assume success unless error

    # Ensure dated playlist exists
    playlist = ensure_playlist_exists(playlist_name)
    if not playlist:
        return (
            ctx,
            False,
            f"❌ Failed to create playlist '{playlist_name}'",
        )

    # Add to playlist
    try:
        if playlists.add_track_to_playlist(playlist["id"], track_id):
            # Success
            log(f"   ✓ Added to {playlist_name}", level="info")
            return ctx, True, f"👍 Liked {display_name}\n+ Added to {playlist_name}"
        else:
            # Already in playlist
            log(f"   • Already in {playlist_name}", level="info")
            return ctx, True, f"👍 Liked {display_name}\n(Already in {playlist_name})"
    except Exception as e:
        log(f"   ✗ Failed to add to {playlist_name}: {str(e)}", level="error")
        return (
            ctx,
            False,
            f"❌ Failed to add to {playlist_name}: {str(e)}",
        )


def execute_add_not_quite(ctx: AppContext) -> Tuple[AppContext, bool, str]:
    """
    Add current track to "Not Quite" playlist.

    Args:
        ctx: Application context

    Returns:
        (updated_context, success, message)
    """
    # Get current track info
    track_info = get_current_track_info(ctx)
    if not track_info:
        return ctx, False, "❌ No track playing"

    track_id, db_track, current_track = track_info
    display_name = library.get_display_name(current_track)

    # Get playlist name from config (default to "Not Quite")
    playlist_name = (
        ctx.config.hotkeys.not_quite_playlist
        if hasattr(ctx.config, "hotkeys")
        else "Not Quite"
    )

    # Remove from reposts playlist (if exists)
    try:
        reposts_playlist = playlists.get_playlist_by_name("reposts")
        if reposts_playlist:
            logger.info("Track ID:", track_id)
            removed = playlists.remove_track_from_playlist(
                reposts_playlist["id"], track_id
            )
            if removed:
                logger.info(f"Removed track {track_id} from reposts playlist")
    except Exception as e:
        logger.exception(f"Failed to remove track {track_id} from reposts playlist")
        log(f"Warning: Failed to remove from reposts: {str(e)}", level="warning")

    # Ensure playlist exists
    playlist = ensure_playlist_exists(playlist_name)
    if not playlist:
        return ctx, False, f"❌ Failed to create playlist '{playlist_name}'"

    # Add to playlist
    try:
        if playlists.add_track_to_playlist(playlist["id"], track_id):
            return ctx, True, f"🤔 Added {display_name}\nto {playlist_name}"
        else:
            return ctx, True, f"🤔 {display_name}\n(Already in {playlist_name})"
    except Exception as e:
        return ctx, False, f"❌ Failed to add to {playlist_name}: {str(e)}"


def execute_add_not_interested_and_skip(
    ctx: AppContext,
) -> Tuple[AppContext, bool, str]:
    """
    Skip current track and add to "Not Interested" playlist.

    Args:
        ctx: Application context

    Returns:
        (updated_context, success, message)
    """
    # Get current track info BEFORE skipping
    track_info = get_current_track_info(ctx)
    if not track_info:
        return ctx, False, "❌ No track playing"

    track_id, db_track, current_track = track_info
    display_name = library.get_display_name(current_track)

    # Get playlist name from config (default to "Not Interested")
    playlist_name = (
        ctx.config.hotkeys.not_interested_playlist
        if hasattr(ctx.config, "hotkeys")
        else "Not Interested"
    )

    # Skip to next track IMMEDIATELY (before playlist operations)
    ctx, _ = playback.handle_skip_command(ctx)

    # Remove from reposts playlist (if exists)
    try:
        reposts_playlist = playlists.get_playlist_by_name("reposts")
        if reposts_playlist:
            removed = playlists.remove_track_from_playlist(
                reposts_playlist["id"], track_id
            )
            if removed:
                logger.info(f"Removed track {track_id} from reposts playlist")
    except Exception as e:
        logger.exception(f"Failed to remove track {track_id} from reposts playlist")
        log(f"Warning: Failed to remove from reposts: {str(e)}", level="warning")

    # Ensure playlist exists
    playlist = ensure_playlist_exists(playlist_name)
    if not playlist:
        return ctx, False, f"❌ Skipped\nFailed to create playlist '{playlist_name}'"

    # Add to playlist (after skip)
    add_success = False
    try:
        if playlists.add_track_to_playlist(playlist["id"], track_id):
            add_success = True
        else:
            add_success = True  # Already in playlist is still success
    except Exception as e:
        return ctx, False, f"❌ Skipped\nFailed to add to {playlist_name}: {str(e)}"

    if add_success:
        return ctx, True, f"⏭️ Skipped\n+ Added {display_name}\nto {playlist_name}"
    else:
        return ctx, False, f"❌ Skipped\nFailed to add {display_name}"


# Action registry for routing
ACTIONS = {
    "like_and_add_dated": execute_like_and_add_dated,
    "add_not_quite": execute_add_not_quite,
    "add_not_interested_and_skip": execute_add_not_interested_and_skip,
}


def execute_composite_action(
    ctx: AppContext, action_name: str
) -> Tuple[AppContext, bool, str]:
    """
    Execute a composite action by name.

    Args:
        ctx: Application context
        action_name: Name of action to execute

    Returns:
        (updated_context, success, message)
    """
    if action_name not in ACTIONS:
        return ctx, False, f"❌ Unknown action: {action_name}"

    action_func = ACTIONS[action_name]
    return action_func(ctx)
