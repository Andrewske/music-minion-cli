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
        database.add_rating(track_id, 'like', 'User liked song')
        print(f"👍 Liked: {library.get_display_name(current_track)}")

        # Show temporal context
        now = datetime.now()
        time_context = f"{now.strftime('%A')} at {now.hour:02d}:{now.minute:02d}"
        print(f"   Liked on {time_context}")
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
