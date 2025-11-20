"""
Rating command handlers for Music Minion CLI.

Handles: archive, like, love, note
"""

from typing import List, Tuple
from datetime import datetime

from music_minion.context import AppContext
from music_minion.core import database
from music_minion.domain import library


def handle_archive_command(ctx: AppContext) -> Tuple[AppContext, bool]:
    """Handle archive command - mark current song to never play again.

    Args:
        ctx: Application context

    Returns:
        (updated_context, should_continue)
    """
    if not ctx.player_state.current_track:
        print("No track is currently playing")
        return ctx, True

    # Find current track
    current_track = None
    for track in ctx.music_tracks:
        if track.local_path == ctx.player_state.current_track:
            current_track = track
            break

    if not current_track:
        print("Could not find current track information")
        return ctx, True

    # Get track ID and add archive rating
    db_track = database.get_track_by_path(ctx.player_state.current_track)
    if db_track:
        track_id = db_track['id']
        database.add_rating(track_id, 'archive', 'User archived song')
        print(f"📦 Archived: {library.get_display_name(current_track)}")
        print("   This song will not be played in future shuffle sessions")

        # Skip to next track automatically
        from .playback import handle_skip_command
        return handle_skip_command(ctx)
    else:
        print("Failed to archive track")

    return ctx, True


def handle_like_command(ctx: AppContext) -> Tuple[AppContext, bool]:
    """Handle like command - rate current song as liked.

    Args:
        ctx: Application context

    Returns:
        (updated_context, should_continue)
    """
    if not ctx.player_state.current_track:
        print("No track is currently playing")
        return ctx, True

    # Find current track
    current_track = None
    for track in ctx.music_tracks:
        if track.local_path == ctx.player_state.current_track:
            current_track = track
            break

    if not current_track:
        print("Could not find current track information")
        return ctx, True

    # Get track ID and add like rating
    db_track = database.get_track_by_path(ctx.player_state.current_track)
    if db_track:
        track_id = db_track['id']
        database.add_rating(track_id, 'like', 'User liked song', source='user')
        print(f"👍 Liked: {library.get_display_name(current_track)}")

        # Show temporal context
        now = datetime.now()
        time_context = f"{now.strftime('%A')} at {now.hour:02d}:{now.minute:02d}"
        print(f"   Liked on {time_context}")

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
                            print("   ✓ Synced like to SoundCloud")
                        else:
                            print(f"   ⚠ Failed to sync to SoundCloud: {error_msg}")
                            print("     Check logs for details")
                    else:
                        # Not authenticated - skip silently
                        pass
                except Exception as e:
                    print(f"   ⚠ Error syncing to SoundCloud: {e}")
                    print("     Check logs for details")
    else:
        print("Failed to rate track")

    return ctx, True


def handle_love_command(ctx: AppContext) -> Tuple[AppContext, bool]:
    """Handle love command - rate current song as loved.

    Args:
        ctx: Application context

    Returns:
        (updated_context, should_continue)
    """
    if not ctx.player_state.current_track:
        print("No track is currently playing")
        return ctx, True

    # Find current track
    current_track = None
    for track in ctx.music_tracks:
        if track.local_path == ctx.player_state.current_track:
            current_track = track
            break

    if not current_track:
        print("Could not find current track information")
        return ctx, True

    # Get track ID and add love rating
    db_track = database.get_track_by_path(ctx.player_state.current_track)
    if db_track:
        track_id = db_track['id']
        database.add_rating(track_id, 'love', 'User loved song')
        print(f"❤️  Loved: {library.get_display_name(current_track)}")

        # Show temporal context and DJ info
        now = datetime.now()
        time_context = f"{now.strftime('%A')} at {now.hour:02d}:{now.minute:02d}"
        print(f"   Loved on {time_context}")

        dj_info = library.get_dj_info(current_track)
        if dj_info != "No DJ metadata":
            print(f"   {dj_info}")
    else:
        print("Failed to rate track")

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
        print("Error: Please provide a note. Usage: note <text>")
        return ctx, True

    if not ctx.player_state.current_track:
        print("No track is currently playing")
        return ctx, True

    # Find current track
    current_track = None
    for track in ctx.music_tracks:
        if track.local_path == ctx.player_state.current_track:
            current_track = track
            break

    if not current_track:
        print("Could not find current track information")
        return ctx, True

    # Get track ID and add note
    db_track = database.get_track_by_path(ctx.player_state.current_track)
    if db_track:
        track_id = db_track['id']
        note_text = ' '.join(args)
        note_id = database.add_note(track_id, note_text)

        print(f"📝 Note added to: {library.get_display_name(current_track)}")
        print(f"   \"{note_text}\"")

        # Show temporal context
        now = datetime.now()
        time_context = f"{now.strftime('%A')} at {now.hour:02d}:{now.minute:02d}"
        print(f"   Added on {time_context}")

        if note_id:
            print(f"   Note ID: {note_id} (for AI processing)")
    else:
        print("Failed to add note")

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
        print("No track is currently playing")
        return ctx, True

    # Find current track
    current_track = None
    for track in ctx.music_tracks:
        if track.local_path == ctx.player_state.current_track:
            current_track = track
            break

    if not current_track:
        print("Could not find current track information")
        return ctx, True

    # Get track from database
    db_track = database.get_track_by_path(ctx.player_state.current_track)
    if not db_track:
        print("Could not find track in database")
        return ctx, True

    track_id = db_track['id']
    soundcloud_id = db_track.get('soundcloud_id')

    # Check if track has SoundCloud like marker
    if not database.has_soundcloud_like(track_id):
        print(f"⚠ {library.get_display_name(current_track)}")
        print("   Track is not liked on SoundCloud")
        return ctx, True

    # Track has SoundCloud like, proceed to unlike
    if not soundcloud_id:
        print(f"⚠ {library.get_display_name(current_track)}")
        print("   Track has like marker but no SoundCloud ID")
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
            print("⚠ Not authenticated with SoundCloud")
            print("   Run: library auth soundcloud")
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

            print(f"💔 Unliked on SoundCloud: {library.get_display_name(current_track)}")
            print("   ✓ Removed like from SoundCloud")
        else:
            print(f"⚠ Failed to unlike on SoundCloud: {error_msg}")
            print("   Check logs for details")

    except Exception as e:
        print(f"⚠ Error unliking on SoundCloud: {e}")
        print("   Check logs for details")

    return ctx, True
