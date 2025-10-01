"""
Rating command handlers for Music Minion CLI.

Handles: archive, like, love, note
"""

from typing import List
from datetime import datetime

from ..core import database
from ..domain import library


def get_player_state():
    """Get current player state from main module."""
    from .. import main
    return main.current_player_state


def get_music_tracks():
    """Get music tracks from main module."""
    from .. import main
    return main.music_tracks


def get_current_track_id():
    """Get current track database ID."""
    from .. import main
    return main.get_current_track_id()


def handle_skip_command():
    """Import skip command from playback module."""
    from .playback import handle_skip_command as skip
    return skip()


def handle_archive_command() -> bool:
    """Handle archive command - mark current song to never play again."""
    current_player_state = get_player_state()
    music_tracks = get_music_tracks()

    if not current_player_state.current_track:
        print("No track is currently playing")
        return True

    # Find current track
    current_track = None
    for track in music_tracks:
        if track.file_path == current_player_state.current_track:
            current_track = track
            break

    if not current_track:
        print("Could not find current track information")
        return True

    # Get track ID and add archive rating
    track_id = get_current_track_id()
    if track_id:
        database.add_rating(track_id, 'archive', 'User archived song')
        print(f"📦 Archived: {library.get_display_name(current_track)}")
        print("   This song will not be played in future shuffle sessions")

        # Skip to next track automatically
        return handle_skip_command()
    else:
        print("Failed to archive track")

    return True


def handle_like_command() -> bool:
    """Handle like command - rate current song as liked."""
    current_player_state = get_player_state()
    music_tracks = get_music_tracks()

    if not current_player_state.current_track:
        print("No track is currently playing")
        return True

    # Find current track
    current_track = None
    for track in music_tracks:
        if track.file_path == current_player_state.current_track:
            current_track = track
            break

    if not current_track:
        print("Could not find current track information")
        return True

    # Get track ID and add like rating
    track_id = get_current_track_id()
    if track_id:
        database.add_rating(track_id, 'like', 'User liked song')
        print(f"👍 Liked: {library.get_display_name(current_track)}")

        # Show temporal context
        now = datetime.now()
        time_context = f"{now.strftime('%A')} at {now.hour:02d}:{now.minute:02d}"
        print(f"   Liked on {time_context}")
    else:
        print("Failed to rate track")

    return True


def handle_love_command() -> bool:
    """Handle love command - rate current song as loved."""
    current_player_state = get_player_state()
    music_tracks = get_music_tracks()

    if not current_player_state.current_track:
        print("No track is currently playing")
        return True

    # Find current track
    current_track = None
    for track in music_tracks:
        if track.file_path == current_player_state.current_track:
            current_track = track
            break

    if not current_track:
        print("Could not find current track information")
        return True

    # Get track ID and add love rating
    track_id = get_current_track_id()
    if track_id:
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

    return True


def handle_note_command(args: List[str]) -> bool:
    """Handle note command - add a note to the current song."""
    current_player_state = get_player_state()
    music_tracks = get_music_tracks()

    if not args:
        print("Error: Please provide a note. Usage: note <text>")
        return True

    if not current_player_state.current_track:
        print("No track is currently playing")
        return True

    # Find current track
    current_track = None
    for track in music_tracks:
        if track.file_path == current_player_state.current_track:
            current_track = track
            break

    if not current_track:
        print("Could not find current track information")
        return True

    # Get track ID and add note
    track_id = get_current_track_id()
    if track_id:
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

    return True
