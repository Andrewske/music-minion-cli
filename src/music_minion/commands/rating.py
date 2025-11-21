"""
Rating command handlers for Music Minion CLI.

Handles: archive, like, love, note
"""

from typing import List, Tuple
from datetime import datetime

from loguru import logger

from music_minion.context import AppContext
from music_minion.core import database
from music_minion.core.output import log
from music_minion.domain import library


def handle_archive_command(ctx: AppContext) -> Tuple[AppContext, bool]:
    """Handle archive command - mark current song to never play again.

    Args:
        ctx: Application context

    Returns:
        (updated_context, should_continue)
    """
    if not ctx.player_state.current_track:
        log("No track is currently playing", level="warning")
        return ctx, True

    # Get track ID from player state (works for both local and streaming tracks)
    track_id = ctx.player_state.current_track_id

    # Fallback to path lookup for backward compatibility
    if not track_id:
        db_track = database.get_track_by_path(ctx.player_state.current_track)
        if not db_track:
            log("❌ Could not find current track in database", level="error")
            return ctx, True
        track_id = db_track['id']

    # Get full track info from database
    db_track = database.get_track_by_id(track_id)
    if not db_track:
        log("❌ Could not find current track in database", level="error")
        return ctx, True

    # Find Track object in memory for display (multi-source lookup)
    current_track = None
    for track in ctx.music_tracks:
        if (track.local_path and track.local_path == db_track.get('local_path')) or \
           (track.soundcloud_id and track.soundcloud_id == db_track.get('soundcloud_id')) or \
           (track.spotify_id and track.spotify_id == db_track.get('spotify_id')) or \
           (track.youtube_id and track.youtube_id == db_track.get('youtube_id')):
            current_track = track
            break

    if not current_track:
        log("Could not find current track information", level="error")
        return ctx, True

    # Add archive rating
    database.add_rating(track_id, 'archive', 'User archived song')
    log(f"📦 Archived: {library.get_display_name(current_track)}", level="info")
    log("   This song will not be played in future shuffle sessions", level="info")

    # Skip to next track automatically
    from .playback import handle_skip_command
    return handle_skip_command(ctx)


def handle_like_command(ctx: AppContext) -> Tuple[AppContext, bool]:
    """Handle like command - rate current song as liked.

    Args:
        ctx: Application context

    Returns:
        (updated_context, should_continue)
    """
    if not ctx.player_state.current_track:
        log("No track is currently playing", level="warning")
        return ctx, True

    # Get track ID from player state (works for both local and streaming tracks)
    track_id = ctx.player_state.current_track_id

    # Fallback to path lookup for backward compatibility
    if not track_id:
        db_track = database.get_track_by_path(ctx.player_state.current_track)
        if not db_track:
            log("❌ Could not find current track in database", level="error")
            return ctx, True
        track_id = db_track['id']

    # Get full track info from database
    db_track = database.get_track_by_id(track_id)
    if not db_track:
        log("❌ Could not find current track in database", level="error")
        return ctx, True

    # Find Track object in memory for display (multi-source lookup)
    current_track = None
    for track in ctx.music_tracks:
        if (track.local_path and track.local_path == db_track.get('local_path')) or \
           (track.soundcloud_id and track.soundcloud_id == db_track.get('soundcloud_id')) or \
           (track.spotify_id and track.spotify_id == db_track.get('spotify_id')) or \
           (track.youtube_id and track.youtube_id == db_track.get('youtube_id')):
            current_track = track
            break

    if not current_track:
        log("Could not find current track information", level="error")
        return ctx, True

    # Add like rating
    database.add_rating(track_id, 'like', 'User liked song', source='user')
    log(f"👍 Liked: {library.get_display_name(current_track)}", level="info")

    # Show temporal context
    now = datetime.now()
    time_context = f"{now.strftime('%A')} at {now.hour:02d}:{now.minute:02d}"
    log(f"   Liked on {time_context}", level="info")

    # Sync to SoundCloud if track has soundcloud_id
    soundcloud_id = db_track.get('soundcloud_id')
    if soundcloud_id:
        # Check if already liked on SoundCloud
        if not database.has_soundcloud_like(track_id):
            # Sync like to SoundCloud
            from music_minion.domain.library import providers

            try:
                # Get SoundCloud provider
                provider = providers.get_provider('soundcloud')
                from music_minion.domain.library.provider import ProviderConfig
                config = ProviderConfig(name='soundcloud', enabled=True)
                state = provider.init_provider(config)

                if state.authenticated:
                    # Call API to like track
                    new_state, success, error_msg = provider.like_track(state, soundcloud_id)

                    if success:
                        # Add soundcloud marker to database
                        database.add_rating(track_id, 'like', 'Synced to SoundCloud', source='soundcloud')
                        log("   ✓ Synced like to SoundCloud", level="info")
                    else:
                        log(f"   ⚠ Failed to sync to SoundCloud: {error_msg}", level="warning")
                        log("     Check logs for details", level="warning")
                else:
                    # Not authenticated - skip silently
                    pass
            except Exception as e:
                log(f"   ⚠ Error syncing to SoundCloud: {e}", level="warning")
                log("     Check logs for details", level="warning")

    return ctx, True


def handle_love_command(ctx: AppContext) -> Tuple[AppContext, bool]:
    """Handle love command - rate current song as loved.

    Args:
        ctx: Application context

    Returns:
        (updated_context, should_continue)
    """
    if not ctx.player_state.current_track:
        log("No track is currently playing", level="warning")
        return ctx, True

    # Get track ID from player state (works for both local and streaming tracks)
    track_id = ctx.player_state.current_track_id

    # Fallback to path lookup for backward compatibility
    if not track_id:
        db_track = database.get_track_by_path(ctx.player_state.current_track)
        if not db_track:
            log("❌ Could not find current track in database", level="error")
            return ctx, True
        track_id = db_track['id']

    # Get full track info from database
    db_track = database.get_track_by_id(track_id)
    if not db_track:
        log("❌ Could not find current track in database", level="error")
        return ctx, True

    # Find Track object in memory for display (multi-source lookup)
    current_track = None
    for track in ctx.music_tracks:
        if (track.local_path and track.local_path == db_track.get('local_path')) or \
           (track.soundcloud_id and track.soundcloud_id == db_track.get('soundcloud_id')) or \
           (track.spotify_id and track.spotify_id == db_track.get('spotify_id')) or \
           (track.youtube_id and track.youtube_id == db_track.get('youtube_id')):
            current_track = track
            break

    if not current_track:
        log("Could not find current track information", level="error")
        return ctx, True

    # Add love rating
    database.add_rating(track_id, 'love', 'User loved song')
    log(f"❤️  Loved: {library.get_display_name(current_track)}", level="info")

    # Show temporal context and DJ info
    now = datetime.now()
    time_context = f"{now.strftime('%A')} at {now.hour:02d}:{now.minute:02d}"
    log(f"   Loved on {time_context}", level="info")

    dj_info = library.get_dj_info(current_track)
    if dj_info != "No DJ metadata":
        log(f"   {dj_info}", level="info")

    return ctx, True


def handle_note_command(ctx: AppContext, args: List[str]) -> Tuple[AppContext, bool]:
    """Handle note command - add a note to the current song.

    Args:
        ctx: Application context
        args: Command arguments

    Returns:
        (updated_context, should_continue)
    """
    if not args:
        log("Error: Please provide a note. Usage: note <text>", level="error")
        return ctx, True

    if not ctx.player_state.current_track:
        log("No track is currently playing", level="warning")
        return ctx, True

    # Get track ID from player state (works for both local and streaming tracks)
    track_id = ctx.player_state.current_track_id

    # Fallback to path lookup for backward compatibility
    if not track_id:
        db_track = database.get_track_by_path(ctx.player_state.current_track)
        if not db_track:
            log("❌ Could not find current track in database", level="error")
            return ctx, True
        track_id = db_track['id']

    # Get full track info from database
    db_track = database.get_track_by_id(track_id)
    if not db_track:
        log("❌ Could not find current track in database", level="error")
        return ctx, True

    # Find Track object in memory for display (multi-source lookup)
    current_track = None
    for track in ctx.music_tracks:
        if (track.local_path and track.local_path == db_track.get('local_path')) or \
           (track.soundcloud_id and track.soundcloud_id == db_track.get('soundcloud_id')) or \
           (track.spotify_id and track.spotify_id == db_track.get('spotify_id')) or \
           (track.youtube_id and track.youtube_id == db_track.get('youtube_id')):
            current_track = track
            break

    if not current_track:
        log("Could not find current track information", level="error")
        return ctx, True

    # Add note
    note_text = ' '.join(args)
    note_id = database.add_note(track_id, note_text)

    log(f"📝 Note added to: {library.get_display_name(current_track)}", level="info")
    log(f"   \"{note_text}\"", level="info")

    # Show temporal context
    now = datetime.now()
    time_context = f"{now.strftime('%A')} at {now.hour:02d}:{now.minute:02d}"
    log(f"   Added on {time_context}", level="info")

    if note_id:
        log(f"   Note ID: {note_id} (for AI processing)", level="info")

    return ctx, True


def handle_unlike_command(ctx: AppContext) -> Tuple[AppContext, bool]:
    """Handle unlike command - remove SoundCloud like for current track.

    Only removes the SoundCloud like marker and syncs to SoundCloud.
    Does not remove local user likes (those are temporal data).

    Args:
        ctx: Application context

    Returns:
        (updated_context, should_continue)
    """
    if not ctx.player_state.current_track:
        log("No track is currently playing", level="warning")
        return ctx, True

    # Get track ID from player state (works for both local and streaming tracks)
    track_id = ctx.player_state.current_track_id

    # Fallback to path lookup for backward compatibility
    if not track_id:
        db_track = database.get_track_by_path(ctx.player_state.current_track)
        if not db_track:
            log("❌ Could not find current track in database", level="error")
            return ctx, True
        track_id = db_track['id']

    # Get full track info from database
    db_track = database.get_track_by_id(track_id)
    if not db_track:
        log("❌ Could not find current track in database", level="error")
        return ctx, True

    # Find Track object in memory for display (multi-source lookup)
    current_track = None
    for track in ctx.music_tracks:
        if (track.local_path and track.local_path == db_track.get('local_path')) or \
           (track.soundcloud_id and track.soundcloud_id == db_track.get('soundcloud_id')) or \
           (track.spotify_id and track.spotify_id == db_track.get('spotify_id')) or \
           (track.youtube_id and track.youtube_id == db_track.get('youtube_id')):
            current_track = track
            break

    if not current_track:
        log("Could not find current track information", level="error")
        return ctx, True

    soundcloud_id = db_track.get('soundcloud_id')

    # Check if track has SoundCloud like marker
    if not database.has_soundcloud_like(track_id):
        log(f"⚠ {library.get_display_name(current_track)}", level="warning")
        log("   Track is not liked on SoundCloud", level="warning")
        return ctx, True

    # Track has SoundCloud like, proceed to unlike
    if not soundcloud_id:
        log(f"⚠ {library.get_display_name(current_track)}", level="warning")
        log("   Track has like marker but no SoundCloud ID", level="warning")
        return ctx, True

    # Remove SoundCloud like via API
    from music_minion.domain.library import providers

    try:
        # Get SoundCloud provider
        provider = providers.get_provider('soundcloud')
        from music_minion.domain.library.provider import ProviderConfig
        config = ProviderConfig(name='soundcloud', enabled=True)
        state = provider.init_provider(config)

        if not state.authenticated:
            log("⚠ Not authenticated with SoundCloud", level="warning")
            log("   Run: library auth soundcloud", level="warning")
            return ctx, True

        # Call API to unlike track
        new_state, success, error_msg = provider.unlike_track(state, soundcloud_id)

        if success:
            # Remove soundcloud marker from database
            with database.get_db_connection() as conn:
                conn.execute(
                    "DELETE FROM ratings WHERE track_id = ? AND source = 'soundcloud'",
                    (track_id,),
                )
                conn.commit()

            log(f"💔 Unliked on SoundCloud: {library.get_display_name(current_track)}", level="info")
            log("   ✓ Removed like from SoundCloud", level="info")
        else:
            log(f"⚠ Failed to unlike on SoundCloud: {error_msg}", level="warning")
            log("   Check logs for details", level="warning")

    except Exception as e:
        log(f"⚠ Error unliking on SoundCloud: {e}", level="warning")
        log("   Check logs for details", level="warning")

    return ctx, True
