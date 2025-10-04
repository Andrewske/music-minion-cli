"""
Playback command handlers for Music Minion CLI.

Handles: play, pause, resume, stop, skip, shuffle, status
"""

from pathlib import Path
from typing import List, Optional, Tuple

from music_minion.context import AppContext
from music_minion.core import database
from music_minion.domain import library
from music_minion.domain import playback
from music_minion.domain import playlists


def safe_print(ctx: AppContext, message: str, style: Optional[str] = None) -> None:
    """Print using Rich Console if available."""
    if ctx.console:
        if style:
            ctx.console.print(message, style=style)
        else:
            ctx.console.print(message)
    else:
        print(message)


def get_available_tracks(ctx: AppContext) -> List[library.Track]:
    """Get available tracks (respects active playlist and excludes archived)."""
    # Get archived track IDs
    archived_ids = set(database.get_archived_tracks())

    # Get path-to-id mapping for all tracks (single query instead of N queries)
    path_to_id = database.get_track_path_to_id_map()

    # Filter by active playlist if set
    active = playlists.get_active_playlist()
    if active:
        playlist_tracks = playlists.get_playlist_tracks(active['id'])
        playlist_paths = {t['file_path'] for t in playlist_tracks}
        available = [
            t for t in ctx.music_tracks
            if t.file_path in playlist_paths
        ]
    else:
        available = ctx.music_tracks

    # Exclude archived tracks using O(1) dictionary lookups
    filtered = []
    for t in available:
        track_id = path_to_id.get(t.file_path)
        # Include if not in DB yet, or in DB but not archived
        if track_id is None or track_id not in archived_ids:
            filtered.append(t)

    return filtered


def play_track(ctx: AppContext, track: library.Track, playlist_position: Optional[int] = None) -> Tuple[AppContext, bool]:
    """
    Play a specific track.

    Args:
        ctx: Application context
        track: Track to play
        playlist_position: Optional 0-based position in active playlist

    Returns:
        (updated_context, should_continue)
    """
    # Validate track file exists before attempting playback
    if not Path(track.file_path).exists():
        safe_print(ctx, f"❌ File not found: {track.file_path}", "red")
        safe_print(ctx, "Track may have been moved or deleted", "yellow")
        return ctx, True

    # Start MPV if not running
    if not playback.is_mpv_running(ctx.player_state):
        print("Starting music playback...")
        new_state = playback.start_mpv(ctx.config)
        if not new_state:
            print("Failed to start music player")
            return ctx, True
        ctx = ctx.with_player_state(new_state)

    # Play the track
    new_state, success = playback.play_file(ctx.player_state, track.file_path)
    ctx = ctx.with_player_state(new_state)

    if success:
        safe_print(ctx, f"♪ Now playing: {library.get_display_name(track)}", "cyan")
        if track.duration:
            safe_print(ctx, f"   Duration: {library.get_duration_str(track)}", "blue")

        dj_info = library.get_dj_info(track)
        if dj_info != "No DJ metadata":
            safe_print(ctx, f"   {dj_info}", "magenta")

        # Store track in database
        track_id = database.get_or_create_track(
            track.file_path, track.title, track.artist, track.album,
            track.genre, track.year, track.duration, track.key, track.bpm
        )

        # Start playback session
        database.start_playback_session(track_id)

        # Track position if playing from active playlist
        active = playlists.get_active_playlist()
        if active:
            # Use provided position if available, otherwise compute it
            if playlist_position is not None:
                playback.update_playlist_position(active['id'], track_id, playlist_position)
            else:
                # Only compute position if not provided
                playlist_tracks = playlists.get_playlist_tracks(active['id'])
                position = playback.get_track_position_in_playlist(playlist_tracks, track_id)
                if position is not None:
                    playback.update_playlist_position(active['id'], track_id, position)
    else:
        safe_print(ctx, "❌ Failed to play track", "red")

    return ctx, True


def handle_play_command(ctx: AppContext, args: List[str]) -> Tuple[AppContext, bool]:
    """Handle play command - start playback or play specific track.

    Args:
        ctx: Application context
        args: Command arguments

    Returns:
        (updated_context, should_continue)
    """
    # Check MPV availability
    if not playback.check_mpv_available():
        print("Error: MPV is not installed or not available in PATH.")
        return ctx, True

    # Ensure library is loaded
    if not ctx.music_tracks:
        print("No music library loaded. Please run 'scan' command first.")
        return ctx, True

    # If no arguments, play random track or resume current
    if not args:
        if ctx.player_state.current_track:
            # Resume current track
            new_state, success = playback.resume_playback(ctx.player_state)
            ctx = ctx.with_player_state(new_state)
            if success:
                safe_print(ctx, "▶ Resumed playback", "green")
            else:
                safe_print(ctx, "❌ Failed to resume playback", "red")
        else:
            # Play random track from available (non-archived) tracks
            available_tracks = get_available_tracks(ctx)
            if available_tracks:
                track = library.get_random_track(available_tracks)
                return play_track(ctx, track)
            else:
                print("No tracks available to play (all may be archived)")
    else:
        # Search for track by query
        query = ' '.join(args)
        results = library.search_tracks(ctx.music_tracks, query)

        if results:
            track = results[0]  # Play first match
            print(f"Playing: {library.get_display_name(track)}")
            return play_track(ctx, track)
        else:
            print(f"No tracks found matching: {query}")

    return ctx, True


def handle_pause_command(ctx: AppContext) -> Tuple[AppContext, bool]:
    """Handle pause command.

    Args:
        ctx: Application context

    Returns:
        (updated_context, should_continue)
    """
    if not playback.is_mpv_running(ctx.player_state):
        print("No music is currently playing")
        return ctx, True

    new_state, success = playback.pause_playback(ctx.player_state)
    ctx = ctx.with_player_state(new_state)

    if success:
        print("⏸ Paused")

    else:
        print("Failed to pause playback")

    return ctx, True


def handle_resume_command(ctx: AppContext) -> Tuple[AppContext, bool]:
    """Handle resume command.

    Args:
        ctx: Application context

    Returns:
        (updated_context, should_continue)
    """
    if not playback.is_mpv_running(ctx.player_state):
        print("No music player is running")
        return ctx, True

    new_state, success = playback.resume_playback(ctx.player_state)
    ctx = ctx.with_player_state(new_state)

    if success:
        print("▶ Resumed")
    else:
        print("Failed to resume playback")

    return ctx, True


def get_next_track(ctx: AppContext, available_tracks: List[library.Track]) -> Optional[Tuple[library.Track, Optional[int]]]:
    """
    Get the next track to play based on shuffle mode and active playlist.

    Args:
        ctx: Application context
        available_tracks: List of available (non-archived) tracks

    Returns:
        Tuple of (track, playlist_position) if found, None otherwise
        playlist_position is the 0-based index in the active playlist (or None)
    """
    if not available_tracks:
        return None

    # Check shuffle mode
    shuffle_enabled = playback.get_shuffle_mode()
    active = playlists.get_active_playlist()

    # Sequential mode: play next track in playlist order
    if not shuffle_enabled and active:
        # Get current track ID
        current_track_id = None
        if ctx.player_state.current_track:
            db_track = database.get_track_by_path(ctx.player_state.current_track)
            if db_track:
                current_track_id = db_track['id']

        # Get playlist tracks (in order)
        playlist_tracks = playlists.get_playlist_tracks(active['id'])

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
                    return None

            # Check if track is available (not archived) using O(1) dict lookup
            # Also verify file still exists on disk
            next_track = available_tracks_dict.get(next_db_track['file_path'])
            if next_track and Path(next_track.file_path).exists():
                # Found non-archived track - get its position
                position = playback.get_track_position_in_playlist(playlist_tracks, next_db_track['id'])
                return (next_track, position)

            # Track is archived, continue to next
            current_track_id = next_db_track['id']
            attempts += 1

        # All tracks in playlist are archived
        return None

    # Shuffle mode or no active playlist: random selection
    # Remove current track from options if possible
    if ctx.player_state.current_track and len(available_tracks) > 1:
        available_tracks = [t for t in available_tracks if t.file_path != ctx.player_state.current_track]

    if available_tracks:
        track = library.get_random_track(available_tracks)
        if track:
            return (track, None)

    return None


def handle_skip_command(ctx: AppContext) -> Tuple[AppContext, bool]:
    """Handle skip command - play next track (sequential or random based on shuffle mode).

    Args:
        ctx: Application context

    Returns:
        (updated_context, should_continue)
    """
    # Ensure library is loaded
    if not ctx.music_tracks:
        print("No music library loaded. Please run 'scan' command first.")
        return ctx, True

    # Get available tracks (excluding archived ones)
    available_tracks = get_available_tracks(ctx)

    if not available_tracks:
        print("No more tracks to play (all may be archived)")
        return ctx, True

    # Get next track
    result = get_next_track(ctx, available_tracks)

    if result:
        track, position = result
        # Check shuffle mode for user message
        shuffle_enabled = playback.get_shuffle_mode()
        if shuffle_enabled:
            print("⏭ Skipping to next track...")
        else:
            print("⏭ Next track (sequential)...")
        return play_track(ctx, track, position)
    else:
        # No tracks available
        active = playlists.get_active_playlist()
        if active and not playback.get_shuffle_mode():
            print("No non-archived tracks remaining in playlist")
        else:
            print("No more tracks to play (all may be archived)")
        return ctx, True


def handle_shuffle_command(ctx: AppContext, args: List[str]) -> Tuple[AppContext, bool]:
    """Handle shuffle command - toggle or set shuffle mode.

    Args:
        ctx: Application context
        args: Command arguments (optional: 'on' or 'off')

    Returns:
        (updated_context, should_continue)
    """
    if not args:
        # Toggle current mode
        current = playback.get_shuffle_mode()
        new_mode = not current
        playback.set_shuffle_mode(new_mode)

        if new_mode:
            print("🔀 Shuffle mode enabled (random playback)")
        else:
            print("🔁 Sequential mode enabled (play in order)")
        return ctx, True

    # Handle explicit shuffle on/off
    subcommand = args[0].lower()
    if subcommand == 'on':
        playback.set_shuffle_mode(True)
        print("🔀 Shuffle mode enabled (random playback)")
        return ctx, True
    elif subcommand == 'off':
        playback.set_shuffle_mode(False)
        print("🔁 Sequential mode enabled (play in order)")
        return ctx, True
    else:
        print(f"Unknown shuffle option: '{subcommand}'. Use 'shuffle', 'shuffle on', or 'shuffle off'")
        return ctx, True


def handle_stop_command(ctx: AppContext) -> Tuple[AppContext, bool]:
    """Handle stop command.

    Args:
        ctx: Application context

    Returns:
        (updated_context, should_continue)
    """
    if not playback.is_mpv_running(ctx.player_state):
        print("No music is currently playing")
        return ctx, True

    new_state, success = playback.stop_playback(ctx.player_state)
    ctx = ctx.with_player_state(new_state)

    if success:
        print("⏹ Stopped")
    else:
        print("Failed to stop playback")

    return ctx, True


def handle_status_command(ctx: AppContext) -> Tuple[AppContext, bool]:
    """Handle status command - show current player and track status.

    Args:
        ctx: Application context

    Returns:
        (updated_context, should_continue)
    """
    print("Music Minion Status:")
    print("─" * 40)

    if not playback.is_mpv_running(ctx.player_state):
        print("♪ Player: Not running")
        print("♫ Track: None")
        return ctx, True

    # Get current status from player
    status = playback.get_player_status(ctx.player_state)
    position, duration, percent = playback.get_progress_info(ctx.player_state)

    print(f"♪ Player: {'Playing' if status['playing'] else 'Paused'}")

    if status['file']:
        # Find track info
        current_track = None
        for track in ctx.music_tracks:
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
    active = playlists.get_active_playlist()
    if active:
        print(f"📋 Active Playlist: {active['name']} ({active['type']})")

        # Show position if available and in sequential mode
        shuffle_enabled = playback.get_shuffle_mode()
        saved_position = playback.get_playlist_position(active['id'])

        if saved_position and not shuffle_enabled:
            _, position = saved_position
            # Get total track count
            playlist_tracks = playlists.get_playlist_tracks(active['id'])
            total_tracks = len(playlist_tracks)
            print(f"   Position: {position + 1}/{total_tracks}")
    else:
        print("📋 Active Playlist: None (playing all tracks)")

    # Shuffle mode
    shuffle_enabled = playback.get_shuffle_mode()
    shuffle_mode = "ON (random playback)" if shuffle_enabled else "OFF (sequential playback)"
    print(f"🔀 Shuffle: {shuffle_mode}")

    # Library stats
    if ctx.music_tracks:
        available = get_available_tracks(ctx)
        print(f"📚 Library: {len(ctx.music_tracks)} tracks loaded, {len(available)} available for playback")

    return ctx, True
