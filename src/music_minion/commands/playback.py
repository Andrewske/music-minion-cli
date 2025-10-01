"""
Playback command handlers for Music Minion CLI.

Handles: play, pause, resume, stop, skip, shuffle, status
"""

from pathlib import Path
from typing import List, Optional

from ..core import config
from ..core import database
from ..domain import library
from ..domain import playback
from ..domain import ai
from ..domain import playlists


def get_player_state():
    """Get current player state from main module."""
    from .. import main
    return main.current_player_state


def set_player_state(state):
    """Set player state in main module."""
    from .. import main
    main.current_player_state = state


def get_music_tracks():
    """Get music tracks from main module."""
    from .. import main
    return main.music_tracks


def get_config():
    """Get current config from main module."""
    from .. import main
    return main.current_config


def safe_print(message: str, style: str = None) -> None:
    """Print using Rich Console if available."""
    from .. import main
    main.safe_print(message, style)


def ensure_mpv_available() -> bool:
    """Ensure MPV is available."""
    from .. import main
    return main.ensure_mpv_available()


def ensure_library_loaded() -> bool:
    """Ensure music library is loaded."""
    from .. import main
    return main.ensure_library_loaded()


def get_available_tracks() -> List[library.Track]:
    """Get available tracks (respects active playlist and excludes archived)."""
    from .. import main
    return main.get_available_tracks()


def get_current_track_id() -> Optional[int]:
    """Get current track database ID."""
    from .. import main
    return main.get_current_track_id()


def play_track(track: library.Track, playlist_position: Optional[int] = None) -> bool:
    """
    Play a specific track.

    Args:
        track: Track to play
        playlist_position: Optional 0-based position in active playlist

    Returns:
        True to continue interactive loop
    """
    current_player_state = get_player_state()
    current_config = get_config()

    # Start MPV if not running
    if not playback.is_mpv_running(current_player_state):
        print("Starting music playback...")
        new_state = playback.start_mpv(current_config)
        if not new_state:
            print("Failed to start music player")
            return True
        current_player_state = new_state
        set_player_state(current_player_state)

    # Play the track
    new_state, success = playback.play_file(current_player_state, track.file_path)
    set_player_state(new_state)

    if success:
        safe_print(f"♪ Now playing: {library.get_display_name(track)}", "cyan")
        if track.duration:
            safe_print(f"   Duration: {library.get_duration_str(track)}", "blue")

        dj_info = library.get_dj_info(track)
        if dj_info != "No DJ metadata":
            safe_print(f"   {dj_info}", "magenta")

        # Store track in database
        track_id = database.get_or_create_track(
            track.file_path, track.title, track.artist, track.album,
            track.genre, track.year, track.duration, track.key, track.bpm
        )

        # Start playback session
        database.start_playback_session(track_id)

        # Track position if playing from active playlist
        active = playlist.get_active_playlist()
        if active:
            # Use provided position if available, otherwise compute it
            if playlist_position is not None:
                playback.update_playlist_position(active['id'], track_id, playlist_position)
            else:
                # Only compute position if not provided
                playlist_tracks = playlist.get_playlist_tracks(active['id'])
                position = playback.get_track_position_in_playlist(playlist_tracks, track_id)
                if position is not None:
                    playback.update_playlist_position(active['id'], track_id, position)
    else:
        safe_print("❌ Failed to play track", "red")

    return True


def handle_play_command(args: List[str]) -> bool:
    """Handle play command - start playback or play specific track."""
    current_player_state = get_player_state()
    music_tracks = get_music_tracks()

    if not ensure_mpv_available() or not ensure_library_loaded():
        return True

    # If no arguments, play random track or resume current
    if not args:
        if current_player_state.current_track:
            # Resume current track
            new_state, success = playback.resume_playback(current_player_state)
            set_player_state(new_state)
            if success:
                safe_print("▶ Resumed playback", "green")
            else:
                safe_print("❌ Failed to resume playback", "red")
        else:
            # Play random track from available (non-archived) tracks
            available_tracks = get_available_tracks()
            if available_tracks:
                track = library.get_random_track(available_tracks)
                return play_track(track)
            else:
                print("No tracks available to play (all may be archived)")
    else:
        # Search for track by query
        query = ' '.join(args)
        results = library.search_tracks(music_tracks, query)

        if results:
            track = results[0]  # Play first match
            print(f"Playing: {library.get_display_name(track)}")
            return play_track(track)
        else:
            print(f"No tracks found matching: {query}")

    return True


def handle_pause_command() -> bool:
    """Handle pause command."""
    current_player_state = get_player_state()

    if not playback.is_mpv_running(current_player_state):
        print("No music is currently playing")
        return True

    new_state, success = playback.pause_playback(current_player_state)
    set_player_state(new_state)

    if success:
        print("⏸ Paused")
    else:
        print("Failed to pause playback")

    return True


def handle_resume_command() -> bool:
    """Handle resume command."""
    current_player_state = get_player_state()

    if not playback.is_mpv_running(current_player_state):
        print("No music player is running")
        return True

    new_state, success = playback.resume_playback(current_player_state)
    set_player_state(new_state)

    if success:
        print("▶ Resumed")
    else:
        print("Failed to resume playback")

    return True


def handle_skip_command() -> bool:
    """Handle skip command - play next track (sequential or random based on shuffle mode)."""
    current_player_state = get_player_state()

    if not ensure_library_loaded():
        return True

    # Get available tracks (excluding archived ones)
    available_tracks = get_available_tracks()

    if not available_tracks:
        print("No more tracks to play (all may be archived)")
        return True

    # Check shuffle mode
    shuffle_enabled = playback.get_shuffle_mode()
    active = playlist.get_active_playlist()

    # Sequential mode: play next track in playlist order
    if not shuffle_enabled and active:
        # Get current track ID
        current_track_id = None
        if current_player_state.current_track:
            db_track = database.get_track_by_path(current_player_state.current_track)
            if db_track:
                current_track_id = db_track['id']

        # Get playlist tracks (in order)
        playlist_tracks = playlist.get_playlist_tracks(active['id'])

        # Build dict for O(1) lookups of available tracks by file path
        available_tracks_dict = {t.file_path: t for t in available_tracks}

        # Loop to find next non-archived track
        attempts = 0
        max_attempts = len(playlist_tracks)

        while attempts < max_attempts:
            next_db_track = playback.get_next_sequential_track(playlist_tracks, current_track_id)

            if next_db_track is None:
                # Track not found in playlist
                if current_track_id is not None:
                    # Current track removed from playlist, start from beginning
                    current_track_id = None
                    attempts += 1
                    continue
                else:
                    # Empty playlist or other error
                    break

            # Check if track is available (not archived) using O(1) dict lookup
            next_track = available_tracks_dict.get(next_db_track['file_path'])
            if next_track:
                # Found non-archived track - get its position for optimization
                position = playback.get_track_position_in_playlist(playlist_tracks, next_db_track['id'])
                print("⏭ Next track (sequential)...")
                return play_track(next_track, position)

            # Track is archived, continue to next
            current_track_id = next_db_track['id']
            attempts += 1

        # All tracks in playlist are archived
        print("No non-archived tracks remaining in playlist")
        return True

    # Shuffle mode or no active playlist: random selection
    # Remove current track from options if possible
    if current_player_state.current_track and len(available_tracks) > 1:
        available_tracks = [t for t in available_tracks if t.file_path != current_player_state.current_track]

    if available_tracks:
        track = library.get_random_track(available_tracks)
        if track:
            print("⏭ Skipping to next track...")
            return play_track(track)

    print("No more tracks to play (all may be archived)")
    return True


def handle_shuffle_command(args: List[str]) -> bool:
    """Handle shuffle command - toggle or show shuffle mode."""
    if not args:
        # Show current mode
        shuffle_enabled = playback.get_shuffle_mode()
        mode = "ON (random playback)" if shuffle_enabled else "OFF (sequential playback)"
        print(f"🔀 Shuffle mode: {mode}")
        return True

    # Handle shuffle on/off
    subcommand = args[0].lower()
    if subcommand == 'on':
        playback.set_shuffle_mode(True)
        print("🔀 Shuffle mode enabled (random playback)")
        return True
    elif subcommand == 'off':
        playback.set_shuffle_mode(False)
        print("🔁 Sequential mode enabled (play in order)")
        return True
    else:
        print(f"Unknown shuffle option: '{subcommand}'. Use 'shuffle on' or 'shuffle off'")
        return True


def handle_stop_command() -> bool:
    """Handle stop command."""
    current_player_state = get_player_state()

    if not playback.is_mpv_running(current_player_state):
        print("No music is currently playing")
        return True

    new_state, success = playback.stop_playback(current_player_state)
    set_player_state(new_state)

    if success:
        print("⏹ Stopped")
    else:
        print("Failed to stop playback")

    return True


def handle_status_command() -> bool:
    """Handle status command - show current player and track status."""
    current_player_state = get_player_state()
    music_tracks = get_music_tracks()

    print("Music Minion Status:")
    print("─" * 40)

    if not playback.is_mpv_running(current_player_state):
        print("♪ Player: Not running")
        print("♫ Track: None")
        return True

    # Get current status from player
    status = playback.get_player_status(current_player_state)
    position, duration, percent = playback.get_progress_info(current_player_state)

    print(f"♪ Player: {'Playing' if status['playing'] else 'Paused'}")

    if status['file']:
        # Find track info
        current_track = None
        for track in music_tracks:
            if track.file_path == status['file']:
                current_track = track
                break

        if current_track:
            print(f"♫ Track: {library.get_display_name(current_track)}")

            # Progress bar
            if duration > 0:
                progress_bar = "▓" * int(percent / 5) + "░" * (20 - int(percent / 5))
                print(f"⏱  Progress: [{progress_bar}] {playback.format_time(position)} / {playback.format_time(duration)}")

            # DJ info
            dj_info = library.get_dj_info(current_track)
            if dj_info != "No DJ metadata":
                print(f"🎵 Info: {dj_info}")
        else:
            print(f"♫ Track: {status['file']}")
    else:
        print("♫ Track: None")

    print(f"🔊 Volume: {int(status.get('volume', 0))}%")

    # Active playlist
    active = playlist.get_active_playlist()
    if active:
        print(f"📋 Active Playlist: {active['name']} ({active['type']})")

        # Show position if available and in sequential mode
        shuffle_enabled = playback.get_shuffle_mode()
        saved_position = playback.get_playlist_position(active['id'])

        if saved_position and not shuffle_enabled:
            _, position = saved_position
            # Get total track count
            playlist_tracks = playlist.get_playlist_tracks(active['id'])
            total_tracks = len(playlist_tracks)
            print(f"   Position: {position + 1}/{total_tracks}")
    else:
        print("📋 Active Playlist: None (playing all tracks)")

    # Shuffle mode
    shuffle_enabled = playback.get_shuffle_mode()
    shuffle_mode = "ON (random playback)" if shuffle_enabled else "OFF (sequential playback)"
    print(f"🔀 Shuffle: {shuffle_mode}")

    # Library stats
    if music_tracks:
        available = get_available_tracks()
        print(f"📚 Library: {len(music_tracks)} tracks loaded, {len(available)} available for playback")

    return True
