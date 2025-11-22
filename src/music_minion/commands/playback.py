"""
Playback command handlers for Music Minion CLI.

Handles: play, pause, resume, stop, skip, shuffle, status
"""

from pathlib import Path
from typing import List, Optional, Tuple

from music_minion.context import AppContext
from music_minion.core import database
from music_minion.core.output import log
from music_minion.domain import library, playback, playlists
from music_minion.domain.playback import resolver


def get_available_tracks(ctx: AppContext) -> List[library.Track]:
    """Get available tracks (respects active playlist and excludes archived)."""
    # Get archived track IDs
    archived_ids = set(database.get_archived_tracks())

    # Build track identifier to ID map for archived check (handles both local and provider tracks)
    all_db_tracks = database.get_all_tracks()
    identifier_to_id = {}
    for db_track in all_db_tracks:
        identifier = (
            db_track.get("local_path") or "",
            db_track.get("soundcloud_id") or "",
            db_track.get("spotify_id") or "",
            db_track.get("youtube_id") or "",
        )
        identifier_to_id[identifier] = db_track["id"]

    # Filter by active playlist if set
    active = playlists.get_active_playlist()
    if active:
        playlist_tracks = playlists.get_playlist_tracks(active["id"])

        # Build a set of track identifiers from playlist
        # Use tuple of (local_path, soundcloud_id, spotify_id, youtube_id) for matching
        playlist_identifiers = set()
        for pt in playlist_tracks:
            identifier = (
                pt.get("local_path") or "",
                pt.get("soundcloud_id") or "",
                pt.get("spotify_id") or "",
                pt.get("youtube_id") or "",
            )
            playlist_identifiers.add(identifier)

        # Filter tracks by matching identifiers
        available = []
        for t in ctx.music_tracks:
            track_identifier = (
                t.local_path or "",
                t.soundcloud_id or "",
                t.spotify_id or "",
                t.youtube_id or "",
            )
            if track_identifier in playlist_identifiers:
                available.append(t)
    else:
        available = ctx.music_tracks

    # Exclude archived tracks using O(1) dictionary lookups
    filtered = []
    for t in available:
        track_identifier = (
            t.local_path or "",
            t.soundcloud_id or "",
            t.spotify_id or "",
            t.youtube_id or "",
        )
        track_id = identifier_to_id.get(track_identifier)
        # Include if not in DB yet, or in DB but not archived
        if track_id is None or track_id not in archived_ids:
            filtered.append(t)

    return filtered


def play_track(
    ctx: AppContext, track: library.Track, playlist_position: Optional[int] = None
) -> Tuple[AppContext, bool]:
    """
    Play a specific track.

    Args:
        ctx: Application context
        track: Track to play
        playlist_position: Optional 0-based position in active playlist

    Returns:
        (updated_context, should_continue)
    """
    # Validate track belongs to active library (prevent cross-library playback)
    active_library = database.get_active_provider()
    track_source = None
    if track.local_path:
        track_source = "local"
    elif track.soundcloud_id:
        track_source = "soundcloud"
    elif track.spotify_id:
        track_source = "spotify"
    elif track.youtube_id:
        track_source = "youtube"

    # Check if track source matches active library
    if track_source and active_library != "all" and track_source != active_library:
        log(
            f"❌ Cannot play {track_source} track while in {active_library} library",
            level="error",
        )
        log(f"   Track: {library.get_display_name(track)}", level="warning")
        log(
            f"   Tip: Switch to {track_source} library with 'library active {track_source}'",
            level="info",
        )
        return ctx, True

    # Resolve track to playable URI (handles local files and streaming URLs)
    playback_uri = resolver.resolve_playback_uri(track, ctx.provider_states)

    if not playback_uri:
        log("❌ Cannot play: No playable source available", level="error")
        log(f"   Track: {library.get_display_name(track)}", level="warning")

        # Show available sources
        sources = resolver.get_available_sources(track)
        if sources:
            log(f"   Sources: {', '.join(sources)}", level="warning")

            # Check if streaming sources need authentication
            if "soundcloud" in sources and not ctx.provider_states.get(
                "soundcloud", {}
            ).get("authenticated"):
                log(
                    "   Tip: SoundCloud not authenticated. Run 'library auth soundcloud'",
                    level="info",
                )
            if "spotify" in sources and not ctx.provider_states.get("spotify", {}).get(
                "authenticated"
            ):
                log(
                    "   Tip: Spotify not authenticated. Run 'library auth spotify'",
                    level="info",
                )
        else:
            log("   No sources available for this track", level="warning")

        return ctx, True

    # Find track in database (use provider ID for streaming tracks, local_path for local files)
    # We do this BEFORE playing so we can pass track_id to play_file
    track_id = None
    if track.soundcloud_id:
        db_track = database.get_track_by_provider_id("soundcloud", track.soundcloud_id)
        track_id = db_track["id"] if db_track else None
    elif track.spotify_id:
        db_track = database.get_track_by_provider_id("spotify", track.spotify_id)
        track_id = db_track["id"] if db_track else None
    elif track.youtube_id:
        db_track = database.get_track_by_provider_id("youtube", track.youtube_id)
        track_id = db_track["id"] if db_track else None
    elif track.local_path:
        # For local files, use get_or_create_track
        track_id = database.get_or_create_track(
            track.local_path,
            track.title,
            track.artist,
            track.remix_artist,
            track.album,
            track.genre,
            track.year,
            track.duration,
            track.key,
            track.bpm,
        )

    # Detect Spotify URIs and route to SpotifyPlayer
    if playback_uri.startswith("spotify:"):
        from music_minion.domain.playback.spotify_player import SpotifyPlayer

        # Get or initialize Spotify provider state
        if "spotify" not in ctx.provider_states:
            from music_minion.domain.library.providers import spotify

            spotify_state = spotify.init_provider(ctx.config.spotify)
            ctx = ctx.with_provider_states(
                {**ctx.provider_states, "spotify": spotify_state}
            )

        # Create SpotifyPlayer with preferred device
        spotify_player = SpotifyPlayer(
            ctx.provider_states["spotify"],
            preferred_device_id=ctx.config.spotify.preferred_device_id,
            preferred_device_name=ctx.config.spotify.preferred_device_name,
        )

        # Play via Spotify Connect
        success = spotify_player.play(playback_uri)

        if not success:
            log("❌ Failed to play via Spotify", level="error")
            return ctx, True

        # Store current track ID in player state for continuity with other commands
        # Update player state to mark as playing via Spotify
        new_state = ctx.player_state._replace(
            current_track_id=track_id,
            current_track=playback_uri,
            is_playing=True,
            playback_source="spotify",
        )
        ctx = ctx.with_player_state(new_state)

    else:
        # Standard MPV playback (local files, SoundCloud, YouTube)
        # Start MPV if not running
        if not playback.is_mpv_running(ctx.player_state):
            log("Starting music playback...", "info")
            new_state = playback.start_mpv(ctx.config)
            if not new_state:
                log("Failed to start music player", "error")
                return ctx, True
            ctx = ctx.with_player_state(new_state)

        # Play the track (works for both local files and streaming URLs)
        # Pass track_id so it's available in player state for add/remove commands
        new_state, success = playback.play_file(
            ctx.player_state, playback_uri, track_id
        )
        ctx = ctx.with_player_state(new_state)

    if success:
        log(f"♪ Now playing: {library.get_display_name(track)}", level="info")
        if track.duration:
            log(f"   Duration: {library.get_duration_str(track)}", level="info")

        dj_info = library.get_dj_info(track)
        if dj_info != "No DJ metadata":
            log(f"   {dj_info}", level="info")

        # Start playback session if track found in database
        if track_id:
            database.start_playback_session(track_id)

        # Track position if playing from active playlist
        active = playlists.get_active_playlist()
        if active:
            # Use provided position if available, otherwise compute it
            if playlist_position is not None:
                playback.update_playlist_position(
                    active["id"], track_id, playlist_position
                )
            else:
                # Only compute position if not provided
                playlist_tracks = playlists.get_playlist_tracks(active["id"])
                position = playback.get_track_position_in_playlist(
                    playlist_tracks, track_id
                )
                if position is not None:
                    playback.update_playlist_position(active["id"], track_id, position)
    else:
        log("❌ Failed to play track", level="error")

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
        log("Error: MPV is not installed or not available in PATH.", "error")
        return ctx, True

    # Ensure library is loaded
    if not ctx.music_tracks:
        log("No music library loaded. Please run 'scan' command first.", "warning")
        return ctx, True

    # If no arguments, play random track or resume current
    if not args:
        if ctx.player_state.current_track:
            # Resume current track
            new_state, success = playback.resume_playback(ctx.player_state)
            ctx = ctx.with_player_state(new_state)
            if success:
                log("▶ Resumed playback", level="info")
            else:
                log("❌ Failed to resume playback", level="error")
        else:
            # Play random track from available (non-archived) tracks
            available_tracks = get_available_tracks(ctx)
            if available_tracks:
                track = library.get_random_track(available_tracks)
                return play_track(ctx, track)
            else:
                log("No tracks available to play (all may be archived)", "warning")
    else:
        # Search for track by query
        query = " ".join(args)
        results = library.search_tracks(ctx.music_tracks, query)

        if results:
            track = results[0]  # Play first match

            log(f"Playing: {library.get_display_name(track)}", "info")
            return play_track(ctx, track)
        else:
            log(f"No tracks found matching: {query}", "warning")

    return ctx, True


def handle_pause_command(ctx: AppContext) -> Tuple[AppContext, bool]:
    """Handle pause command.

    Args:
        ctx: Application context

    Returns:
        (updated_context, should_continue)
    """
    # Check if any playback is active
    if not ctx.player_state.playback_source:
        log("No music is currently playing", "warning")
        return ctx, True

    # Route to appropriate player
    if ctx.player_state.playback_source == "spotify":
        from music_minion.domain.playback.spotify_player import SpotifyPlayer

        spotify_player = SpotifyPlayer(
            ctx.provider_states.get("spotify", {}),
            preferred_device_id=ctx.config.spotify.preferred_device_id,
            preferred_device_name=ctx.config.spotify.preferred_device_name,
        )
        success = spotify_player.pause()

        if success:
            new_state = ctx.player_state._replace(is_playing=False)
            ctx = ctx.with_player_state(new_state)
            log("⏸ Paused", "info")
        else:
            log("Failed to pause Spotify playback", "error")

    elif ctx.player_state.playback_source == "mpv":
        if not playback.is_mpv_running(ctx.player_state):
            log("No music is currently playing", "warning")
            return ctx, True

        new_state, success = playback.pause_playback(ctx.player_state)
        ctx = ctx.with_player_state(new_state)

        if success:
            log("⏸ Paused", "info")
        else:
            log("Failed to pause playback", "error")

    return ctx, True


def handle_resume_command(ctx: AppContext) -> Tuple[AppContext, bool]:
    """Handle resume command.

    Args:
        ctx: Application context

    Returns:
        (updated_context, should_continue)
    """
    # Check if any playback is active
    if not ctx.player_state.playback_source:
        log("No music player is running", "warning")
        return ctx, True

    # Route to appropriate player
    if ctx.player_state.playback_source == "spotify":
        from music_minion.domain.playback.spotify_player import SpotifyPlayer

        spotify_player = SpotifyPlayer(
            ctx.provider_states.get("spotify", {}),
            preferred_device_id=ctx.config.spotify.preferred_device_id,
            preferred_device_name=ctx.config.spotify.preferred_device_name,
        )
        success = spotify_player.resume()

        if success:
            new_state = ctx.player_state._replace(is_playing=True)
            ctx = ctx.with_player_state(new_state)
            log("▶ Resumed", "info")
        else:
            log("Failed to resume Spotify playback", "error")

    elif ctx.player_state.playback_source == "mpv":
        if not playback.is_mpv_running(ctx.player_state):
            log("No music player is running", "warning")
            return ctx, True

        new_state, success = playback.resume_playback(ctx.player_state)
        ctx = ctx.with_player_state(new_state)

        if success:
            log("▶ Resumed", "info")
        else:
            log("Failed to resume playback", "error")

    return ctx, True


def get_next_track(
    ctx: AppContext, available_tracks: List[library.Track]
) -> Optional[Tuple[library.Track, Optional[int]]]:
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
        # Get current track ID directly from player state (works for both local and streaming tracks)
        current_track_id = ctx.player_state.current_track_id

        # Get playlist tracks (in order)
        playlist_tracks = playlists.get_playlist_tracks(active["id"])

        # Build dict for O(1) lookups of available tracks using compound identifier
        # (handles both local files and streaming tracks)
        available_tracks_dict = {}
        for t in available_tracks:
            identifier = (
                t.local_path or "",
                t.soundcloud_id or "",
                t.spotify_id or "",
                t.youtube_id or "",
            )
            available_tracks_dict[identifier] = t

        # Loop to find next non-archived track
        attempts = 0
        max_attempts = len(playlist_tracks)

        while attempts < max_attempts:
            next_db_track = playback.get_next_sequential_track(
                playlist_tracks, current_track_id
            )

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

            # Check if track is available (not archived) using O(1) dict lookup with compound identifier
            next_track_identifier = (
                next_db_track.get("local_path") or "",
                next_db_track.get("soundcloud_id") or "",
                next_db_track.get("spotify_id") or "",
                next_db_track.get("youtube_id") or "",
            )
            next_track = available_tracks_dict.get(next_track_identifier)

            # Verify track is playable (file exists for local, or has provider ID for streaming)
            if next_track:
                is_playable = False
                if next_track.local_path and next_track.local_path.strip():
                    # Local track - verify file exists
                    is_playable = Path(next_track.local_path).exists()
                elif (
                    next_track.soundcloud_id
                    or next_track.spotify_id
                    or next_track.youtube_id
                ):
                    # Streaming track - has provider ID, assume playable
                    is_playable = True

                if is_playable:
                    # Found non-archived track - get its position
                    position = playback.get_track_position_in_playlist(
                        playlist_tracks, next_db_track["id"]
                    )
                    return (next_track, position)

            # Track is archived, continue to next
            current_track_id = next_db_track["id"]
            attempts += 1

        # All tracks in playlist are archived
        return None

    # Shuffle mode or no active playlist: random selection
    # Remove current track from options if possible
    if ctx.player_state.current_track and len(available_tracks) > 1:
        available_tracks = [
            t
            for t in available_tracks
            if t.local_path != ctx.player_state.current_track
        ]

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
        log("No music library loaded. Please run 'scan' command first.", "warning")
        return ctx, True

    # Get available tracks (excluding archived ones)
    available_tracks = get_available_tracks(ctx)

    if not available_tracks:
        log("No more tracks to play (all may be archived)", "warning")
        return ctx, True

    # Get next track
    result = get_next_track(ctx, available_tracks)

    if result:
        track, position = result
        # Check shuffle mode for user message
        shuffle_enabled = playback.get_shuffle_mode()
        if shuffle_enabled:
            log("⏭ Skipping to next track...", "info")
        else:
            log("⏭ Next track (sequential)...", "info")
        return play_track(ctx, track, position)
    else:
        # No tracks available
        active = playlists.get_active_playlist()
        if active and not playback.get_shuffle_mode():
            log("No non-archived tracks remaining in playlist", "warning")
        else:
            log("No more tracks to play (all may be archived)", "warning")
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
            log("🔀 Shuffle mode enabled (random playback)", "info")
        else:
            log("🔁 Sequential mode enabled (play in order)", "info")
        return ctx, True

    # Handle explicit shuffle on/off
    subcommand = args[0].lower()
    if subcommand == "on":
        playback.set_shuffle_mode(True)
        log("🔀 Shuffle mode enabled (random playback)", "info")
        return ctx, True
    elif subcommand == "off":
        playback.set_shuffle_mode(False)
        log("🔁 Sequential mode enabled (play in order)", "info")
        return ctx, True
    else:
        log(
            f"Unknown shuffle option: '{subcommand}'. Use 'shuffle', 'shuffle on', or 'shuffle off'",
            "warning",
        )
        return ctx, True


def handle_stop_command(ctx: AppContext) -> Tuple[AppContext, bool]:
    """Handle stop command.

    Args:
        ctx: Application context

    Returns:
        (updated_context, should_continue)
    """
    # Check if any playback is active
    if not ctx.player_state.playback_source:
        log("No music is currently playing", "warning")
        return ctx, True

    # Route to appropriate player
    if ctx.player_state.playback_source == "spotify":
        from music_minion.domain.playback.spotify_player import SpotifyPlayer

        spotify_player = SpotifyPlayer(
            ctx.provider_states.get("spotify", {}),
            preferred_device_id=ctx.config.spotify.preferred_device_id,
            preferred_device_name=ctx.config.spotify.preferred_device_name,
        )
        success = spotify_player.stop()

        if success:
            new_state = ctx.player_state._replace(
                is_playing=False, playback_source=None
            )
            ctx = ctx.with_player_state(new_state)
            log("⏹ Stopped", "info")
        else:
            log("Failed to stop Spotify playback", "error")

    elif ctx.player_state.playback_source == "mpv":
        if not playback.is_mpv_running(ctx.player_state):
            log("No music is currently playing", "warning")
            return ctx, True

        new_state, success = playback.stop_playback(ctx.player_state)
        ctx = ctx.with_player_state(new_state)

        if success:
            log("⏹ Stopped", "info")
        else:
            log("Failed to stop playback", "error")

    return ctx, True


def handle_status_command(ctx: AppContext) -> Tuple[AppContext, bool]:
    """Handle status command - show current player and track status.

    Args:
        ctx: Application context

    Returns:
        (updated_context, should_continue)
    """
    log("Music Minion Status:", "info")
    log("─" * 40, "info")

    if not playback.is_mpv_running(ctx.player_state):
        log("♪ Player: Not running", "info")
        log("♫ Track: None", "info")
        return ctx, True

    # Get current status from player
    status = playback.get_player_status(ctx.player_state)
    position, duration, percent = playback.get_progress_info(ctx.player_state)

    log(f"♪ Player: {'Playing' if status['playing'] else 'Paused'}", "info")

    if status["file"]:
        # Find track info
        current_track = None
        for track in ctx.music_tracks:
            if track.local_path == status["file"]:
                current_track = track
                break

        if current_track:
            log(f"♫ Track: {library.get_display_name(current_track)}", "info")

            # Progress bar
            if duration > 0:
                progress_bar = "▓" * int(percent / 5) + "░" * (20 - int(percent / 5))
                log(
                    f"⏱  Progress: [{progress_bar}] {playback.format_time(position)} / {playback.format_time(duration)}",
                    "info",
                )

            # DJ info
            dj_info = library.get_dj_info(current_track)
            if dj_info != "No DJ metadata":
                log(f"🎵 Info: {dj_info}", "info")
        else:
            log(f"♫ Track: {status['file']}", "info")
    else:
        log("♫ Track: None", "info")

    log(f"🔊 Volume: {int(status.get('volume', 0))}%", "info")

    # Active playlist
    active = playlists.get_active_playlist()
    if active:
        log(f"📋 Active Playlist: {active['name']} ({active['type']})", "info")

        # Show position if available and in sequential mode
        shuffle_enabled = playback.get_shuffle_mode()
        saved_position = playback.get_playlist_position(active["id"])

        if saved_position and not shuffle_enabled:
            _, position = saved_position
            # Get total track count
            playlist_tracks = playlists.get_playlist_tracks(active["id"])
            total_tracks = len(playlist_tracks)
            log(f"   Position: {position + 1}/{total_tracks}", "info")
    else:
        log("📋 Active Playlist: None (playing all tracks)", "info")

    # Shuffle mode
    shuffle_enabled = playback.get_shuffle_mode()
    shuffle_mode = (
        "ON (random playback)" if shuffle_enabled else "OFF (sequential playback)"
    )
    log(f"🔀 Shuffle: {shuffle_mode}", "info")

    # Library stats
    if ctx.music_tracks:
        available = get_available_tracks(ctx)
        log(
            f"📚 Library: {len(ctx.music_tracks)} tracks loaded, {len(available)} available for playback",
            "info",
        )

    return ctx, True


def handle_history_command(ctx: AppContext, args: List[str]) -> Tuple[AppContext, bool]:
    """Show playback history in track viewer.

    Args:
        ctx: Application context
        args: Optional limit (default: 50)

    Returns:
        (updated_context, should_continue)
    """
    # Parse limit from args (default: 50)
    limit = 50
    if args and args[0].isdigit():
        limit = int(args[0])

    # Get active library and fetch sessions filtered by source
    active_provider = database.get_active_provider()
    sessions = database.get_recent_playback_sessions(
        limit, source_filter=active_provider
    )

    if not sessions:
        provider_label = active_provider.title() if active_provider != "all" else "All"
        log(f"No playback history found for {provider_label} library", level="info")
        return ctx, True

    # Signal UI to show track viewer with history
    provider_label = active_provider.title() if active_provider != "all" else "All"
    ctx = ctx.with_ui_action(
        {
            "type": "show_track_viewer",
            "tracks": sessions,
            "playlist_name": f"Playback History - {provider_label} (Last {len(sessions)} tracks)",
            "playlist_type": "history",
        }
    )

    return ctx, True
