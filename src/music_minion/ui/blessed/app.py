"""Main event loop and entry point for blessed UI."""

import dataclasses
import queue
import sys
import threading
import time
from pathlib import Path

from blessed import Terminal
from loguru import logger

from music_minion.commands import admin
from music_minion.context import AppContext
from music_minion.core import database
from music_minion.core.output import clear_blessed_mode, set_blessed_mode
from music_minion.ipc import server as ipc_server

from .components import (
    calculate_layout,
    render_analytics_viewer,
    render_dashboard,
    render_history,
    render_input,
    render_palette,
    render_smart_playlist_wizard,
)
from .components.comparison_history import render_comparison_history_viewer
from .components.metadata_editor import render_metadata_editor
from .components.rating_history import render_rating_history_viewer
from .helpers import write_at
from .components.track_viewer import render_track_viewer
from .events.commands import execute_command
from .events.keyboard import handle_key
from .state import PlaylistInfo, UIState, add_history_line, update_track_info

# Frame interval constants for background updates
PLAYER_POLL_INTERVAL = 10  # Poll MPV every 10 frames (~1 second)
SCAN_POLL_INTERVAL = 5  # Poll scan progress every 5 frames (~0.5 seconds)
SYNC_POLL_INTERVAL = 5  # Poll sync progress every 5 frames (~0.5 seconds)
CONVERSION_POLL_INTERVAL = 5  # Poll conversion progress every 5 frames (~0.5 seconds)
POSITION_UPDATE_THRESHOLD = 0.1  # Update display every ~3 Unicode blocks (100ms)


def _check_and_reload_files() -> None:
    """Check for pending file changes and reload if needed."""
    # Import main module to access global file watcher
    from ... import main

    if main.file_watcher_handler:
        try:
            from ... import dev_reload

            ready_files = main.file_watcher_handler.check_pending_changes()
            for filepath in ready_files:
                success = dev_reload.reload_module(filepath)
                if success:
                    filename = Path(filepath).name
                    # Note: Can't use safe_print here as it would interfere with blessed UI
                    # Reload happens silently in blessed mode
        except Exception:
            # Silently ignore errors in hot-reload to not break UI
            pass


def poll_scan_state(ui_state: UIState) -> UIState:
    """
    Poll library scan state and update UI state.

    Args:
        ui_state: Current UI state

    Returns:
        Updated UI state with scan progress
    """
    from dataclasses import replace

    from .state import add_history_line, end_scan, update_scan_progress

    # Get current scan state
    scan_state = admin.get_scan_state()

    if scan_state is None:
        # No scan running, clear scan UI if it was showing
        if ui_state.scan_progress.is_scanning:
            ui_state = end_scan(ui_state)
        return ui_state

    # Update UI state with scan progress
    ui_state = update_scan_progress(
        ui_state,
        files_scanned=scan_state.get("files_scanned", 0),
        current_file=scan_state.get("current_file", ""),
        phase=scan_state.get("phase", "scanning"),
    )

    # Start scan UI if not already showing
    if not ui_state.scan_progress.is_scanning:
        from .state import start_scan

        ui_state = start_scan(ui_state, scan_state.get("total_files", 0))

    # Update total files if changed
    if scan_state.get("total_files", 0) != ui_state.scan_progress.total_files:
        ui_state = replace(
            ui_state,
            scan_progress=replace(
                ui_state.scan_progress, total_files=scan_state.get("total_files", 0)
            ),
        )

    # Check if scan completed
    if scan_state.get("completed", False):
        # End scan UI
        ui_state = end_scan(ui_state)

        # Show results in history
        if scan_state.get("error"):
            ui_state = add_history_line(
                ui_state, f"❌ Scan failed: {scan_state['error']}", "red"
            )
        else:
            tracks = scan_state.get("tracks", [])
            added = scan_state.get("added", 0)
            updated = scan_state.get("updated", 0)
            errors = scan_state.get("errors", 0)
            stats = scan_state.get("stats", {})

            ui_state = add_history_line(ui_state, "✅ Scan complete!", "green")
            ui_state = add_history_line(ui_state, f"  📝 New tracks: {added}", "white")
            ui_state = add_history_line(
                ui_state, f"  🔄 Updated tracks: {updated}", "white"
            )
            if errors:
                ui_state = add_history_line(
                    ui_state, f"  ⚠️  Errors: {errors}", "yellow"
                )

            if stats:
                ui_state = add_history_line(ui_state, "", "white")
                ui_state = add_history_line(ui_state, "📚 Library Overview:", "cyan")
                ui_state = add_history_line(
                    ui_state,
                    f"  Total duration: {stats.get('total_duration_str', 'N/A')}",
                    "white",
                )
                ui_state = add_history_line(
                    ui_state,
                    f"  Total size: {stats.get('total_size_str', 'N/A')}",
                    "white",
                )
                ui_state = add_history_line(
                    ui_state, f"  Artists: {stats.get('artists', 0)}", "white"
                )
                ui_state = add_history_line(
                    ui_state, f"  Albums: {stats.get('albums', 0)}", "white"
                )

        # Clear scan state so completion messages don't repeat on next poll
        admin._clear_scan_state()

    return ui_state


def poll_sync_state(ui_state: UIState) -> UIState:
    """
    Poll library sync state and update UI state.

    Args:
        ui_state: Current UI state

    Returns:
        Updated UI state with sync progress
    """
    from ...commands import library
    from .state import add_history_line

    # Get current sync state
    sync_state = library.get_sync_state()

    if sync_state is None:
        # No sync running
        return ui_state

    # Check if sync completed
    if sync_state.get("completed", False):
        # Show results in history
        provider = sync_state.get("provider", "unknown")
        mode = sync_state.get("mode", "incremental")

        if sync_state.get("error"):
            ui_state = add_history_line(
                ui_state, f"❌ Sync failed: {sync_state['error']}", "red"
            )
        else:
            phase = sync_state.get("phase", "")

            if phase == "playlists" or phase == "syncing_playlists":
                # Playlist sync completed
                stats = sync_state.get("stats", {})
                ui_state = add_history_line(
                    ui_state, f"✅ {provider.title()} playlist sync complete!", "green"
                )
                ui_state = add_history_line(
                    ui_state, f"  ✨ Created: {stats.get('created', 0)}", "white"
                )
                ui_state = add_history_line(
                    ui_state, f"  🔄 Updated: {stats.get('updated', 0)}", "white"
                )
                ui_state = add_history_line(
                    ui_state, f"  ⏭️  Skipped: {stats.get('skipped', 0)}", "white"
                )
                if stats.get("failed", 0) > 0:
                    ui_state = add_history_line(
                        ui_state, f"  ❌ Failed: {stats.get('failed', 0)}", "yellow"
                    )
            else:
                # Library sync completed
                stats = sync_state.get("stats", {})
                mode_str = "full" if mode == "full" else "incremental"
                ui_state = add_history_line(
                    ui_state,
                    f"✅ {provider.title()} sync complete ({mode_str})!",
                    "green",
                )
                ui_state = add_history_line(
                    ui_state, f"  ✨ Created: {stats.get('created', 0)} tracks", "white"
                )
                ui_state = add_history_line(
                    ui_state, f"  ⏭️  Skipped: {stats.get('skipped', 0)} tracks", "white"
                )

        # Clear sync state so completion messages don't repeat on next poll
        library._clear_sync_state()

    else:
        # Sync still running - show progress indicator
        phase = sync_state.get("phase", "")
        provider = sync_state.get("provider", "unknown")

        # Add progress status to UI if not already showing
        # (In the future, we could add a dedicated sync progress UI component)
        # For now, the log messages from the sync functions will show in history

    return ui_state


def poll_conversion_state(ui_state: UIState) -> UIState:
    """
    Poll playlist conversion state and update UI state.

    Args:
        ui_state: Current UI state

    Returns:
        Updated UI state with conversion progress
    """

    from ...commands import playlist
    from .state import add_history_line

    # Get current conversion state
    conversion_state = playlist.get_conversion_state()

    if conversion_state is None:
        # No conversion running
        return ui_state

    # Check if conversion completed
    if conversion_state.get("completed", False):
        # Show results in history
        spotify_name = conversion_state.get("spotify_name", "unknown")
        soundcloud_name = conversion_state.get("soundcloud_name", "unknown")

        if conversion_state.get("error"):
            ui_state = add_history_line(
                ui_state,
                f"❌ Playlist conversion failed: {conversion_state['error']}",
                "red",
            )
        elif conversion_state.get("success"):
            # Conversion completed successfully
            total_tracks = conversion_state.get("total_tracks", 0)
            matched_tracks = conversion_state.get("matched_tracks", 0)
            failed_tracks = conversion_state.get("failed_tracks", 0)
            average_confidence = conversion_state.get("average_confidence", 0.0)
            playlist_url = conversion_state.get("soundcloud_playlist_url", "")
            unmatched_track_names = conversion_state.get("unmatched_track_names", [])

            ui_state = add_history_line(
                ui_state,
                f"✅ Playlist conversion complete: {spotify_name} → {soundcloud_name}",
                "green",
            )

            if total_tracks > 0:
                match_pct = (
                    (matched_tracks / total_tracks * 100) if total_tracks > 0 else 0
                )
                ui_state = add_history_line(
                    ui_state,
                    f"  📊 Matched: {matched_tracks}/{total_tracks} ({match_pct:.1f}%)",
                    "white",
                )

            if matched_tracks > 0:
                ui_state = add_history_line(
                    ui_state,
                    f"  🎯 Avg confidence: {average_confidence:.2f}",
                    "white",
                )

            if playlist_url:
                ui_state = add_history_line(
                    ui_state, f"  🔗 Playlist: {playlist_url}", "white"
                )

            if failed_tracks > 0:
                ui_state = add_history_line(
                    ui_state,
                    f"  ⚠️  {failed_tracks} tracks could not be matched",
                    "yellow",
                )
                # Show first 3 unmatched tracks
                for track_name in unmatched_track_names[:3]:
                    ui_state = add_history_line(
                        ui_state, f"     • {track_name}", "yellow"
                    )
                if len(unmatched_track_names) > 3:
                    remaining = len(unmatched_track_names) - 3
                    ui_state = add_history_line(
                        ui_state, f"     ... and {remaining} more", "yellow"
                    )
        else:
            # Completed but not successful and no error (shouldn't happen)
            ui_state = add_history_line(
                ui_state,
                "⚠️  Playlist conversion completed with unknown status",
                "yellow",
            )

        # Clear conversion state so completion messages don't repeat on next poll
        playlist._clear_conversion_state()

    else:
        # Conversion still running - progress is already logged via background worker
        # (In the future, we could add a dedicated conversion progress UI component)
        pass

    return ui_state


def poll_player_state(ctx: AppContext, ui_state: UIState) -> tuple[AppContext, UIState]:
    """
    Poll player state and update both AppContext and UI state.

    Automatically advances to the next track when the current track finishes.

    Args:
        ctx: Application context with player state
        ui_state: UI state with cached display data

    Returns:
        Tuple of (updated AppContext, updated UIState)
    """
    # Import modules (lazy import to avoid circular deps)
    from dataclasses import replace

    from ...commands.playback import get_available_tracks, get_next_track, play_track
    from ...core import database
    from ...domain.playback import player
    from ...domain.playback import state as playback_state
    from ...domain.playlists import crud as playlists

    # Get player status (handle both MPV and Spotify)
    try:
        # Reuse or create Spotify player for current track
        spotify_player = ctx.spotify_player
        if ctx.player_state.current_track and ctx.player_state.current_track.startswith(
            "spotify:"
        ):
            # Create new instance only if needed
            if not spotify_player:
                from ...domain.playback.spotify_player import SpotifyPlayer

                spotify_state = ctx.provider_states.get("spotify")
                if spotify_state and spotify_state.authenticated:
                    device_id = getattr(ctx, "spotify_device_id", None)
                    spotify_player = SpotifyPlayer(spotify_state, device_id)
                    # Update context with new player instance
                    ctx = dataclasses.replace(ctx, spotify_player=spotify_player)
        elif spotify_player:
            # Clear player if not playing Spotify track
            spotify_player = None
            ctx = dataclasses.replace(ctx, spotify_player=None)

        status = player.get_unified_player_status(ctx.player_state, spotify_player)

        # Update provider state if Spotify player was used (token may have been refreshed)
        if spotify_player:
            ctx = ctx.with_provider_states(
                {**ctx.provider_states, "spotify": spotify_player.provider_state}
            )

        # Update player state in AppContext
        new_player_state = ctx.player_state._replace(
            current_track=status.get("file"),
            is_playing=status.get("playing", False),
            current_position=status.get("position", 0.0),
            duration=status.get("duration", 0.0),
        )
        ctx = ctx.with_player_state(new_player_state)

        # Check if track has finished and auto-advance
        track_changed = False
        if player.is_track_finished(ctx.player_state) and ctx.music_tracks:
            # Get available tracks (excluding archived ones)
            available_tracks = get_available_tracks(ctx)

            if available_tracks:
                # Get next track based on shuffle mode and active playlist
                result = get_next_track(ctx, available_tracks)

                if result:
                    track, position = result
                    # Play next track silently (no print in UI mode)
                    ctx, _ = play_track(ctx, track, position)
                    track_changed = True

                    # Add autoplay notification to command history
                    from ...domain import library

                    ui_state = add_history_line(
                        ui_state,
                        f"♪ Now playing: {library.get_display_name(track)}",
                        "cyan",
                    )
                    if track.duration:
                        ui_state = add_history_line(
                            ui_state,
                            f"   Duration: {library.get_duration_str(track)}",
                            "blue",
                        )

                    dj_info = library.get_dj_info(track)
                    if dj_info != "No DJ metadata":
                        ui_state = add_history_line(
                            ui_state, f"   {dj_info}", "magenta"
                        )

        # If track changed, re-query player status to get new track info
        if track_changed:
            # Use unified player status for both MPV and Spotify
            status = player.get_unified_player_status(ctx.player_state, spotify_player)
            new_player_state = ctx.player_state._replace(
                current_track=status.get("file"),
                is_playing=status.get("playing", False),
                current_position=status.get("position", 0.0),
                duration=status.get("duration", 0.0),
            )
            ctx = ctx.with_player_state(new_player_state)

        # If we have a current track, fetch metadata for UI display
        current_file = status.get("file")
        if current_file:
            # Get track from database (handle both local paths and stream URLs)
            db_track = None

            # Primary: Use track ID if available (set during playback for all track types)
            if ctx.player_state.current_track_id:
                db_track = database.get_track_by_id(ctx.player_state.current_track_id)
            # Fallback: Parse URI/path (for legacy compatibility or edge cases)
            elif "api.soundcloud.com/tracks/" in current_file:
                # Extract SoundCloud track ID from URL
                # Format: https://api.soundcloud.com/tracks/{id}/stream?oauth_token=...
                import re

                match = re.search(r"/tracks/(\d+)", current_file)
                if match:
                    soundcloud_id = match.group(1)
                    db_track = database.get_track_by_provider_id(
                        "soundcloud", soundcloud_id
                    )
            elif "youtube.com/watch" in current_file or "youtu.be/" in current_file:
                # Extract YouTube video ID
                import re

                match = re.search(r"(?:v=|youtu\.be/)([a-zA-Z0-9_-]+)", current_file)
                if match:
                    youtube_id = match.group(1)
                    db_track = database.get_track_by_provider_id("youtube", youtube_id)
            else:
                # Assume local file path
                db_track = database.get_track_by_path(current_file)

            if db_track:
                # Build track data for UI display
                track_data = {
                    "title": db_track.get("title") or "Unknown",
                    "artist": db_track.get("artist") or "Unknown",
                    "remix_artist": db_track.get("remix_artist"),
                    "album": db_track.get("album"),
                    "year": db_track.get("year"),
                    "genre": db_track.get("genre"),
                    "bpm": db_track.get("bpm"),
                    "key": db_track.get("key"),
                }

                # Get additional database info
                tags = database.get_track_tags(db_track["id"])
                notes = database.get_track_notes(db_track["id"])

                track_data.update(
                    {
                        "tags": [t["tag_name"] for t in tags],
                        "notes": notes[0]["note_text"] if notes else "",
                        "rating": db_track.get("rating"),
                        "last_played": db_track.get("last_played"),
                        "play_count": db_track.get("play_count", 0),
                    }
                )

                ui_state = update_track_info(ui_state, track_data)

                # Check if track has SoundCloud like marker (for heart indicator)
                has_sc_like = database.has_soundcloud_like(db_track["id"])
                ui_state = replace(
                    ui_state, current_track_has_soundcloud_like=has_sc_like
                )
            else:
                # Track not in database - clear metadata to show fallback
                ui_state = replace(
                    ui_state,
                    track_metadata=None,
                    track_db_info=None,
                    current_track_has_soundcloud_like=False,
                )
        else:
            # No track playing - clear metadata
            ui_state = replace(
                ui_state,
                track_metadata=None,
                track_db_info=None,
                current_track_has_soundcloud_like=False,
            )

        # Update shuffle mode state from database
        shuffle_enabled = playback_state.get_shuffle_mode()
        ui_state = replace(ui_state, shuffle_enabled=shuffle_enabled)

        # Update playlist info from database
        active = playlists.get_active_playlist()
        if active:
            playlist_tracks = playlists.get_playlist_tracks(active["id"])
            position_info = playback_state.get_playlist_position(active["id"])

            playlist_info = PlaylistInfo(
                id=active["id"],
                name=active["name"],
                type=active["type"],
                track_count=len(playlist_tracks),
                current_position=position_info[1] if position_info else None,
            )
            ui_state = replace(ui_state, playlist_info=playlist_info)
        else:
            # No active playlist
            ui_state = replace(ui_state, playlist_info=PlaylistInfo())

    except (OSError, ConnectionError, IOError):
        # Expected errors - player not running, socket issues
        # Silently continue - UI will show "not playing"
        pass
    except (database.sqlite3.Error, KeyError, ValueError) as e:
        # Database or data errors - log but don't crash
        logger.warning(f"Error polling player state: {e}")
    except Exception as e:
        # Unexpected errors - log for debugging
        logger.error(f"Unexpected error polling: {type(e).__name__}: {e}")

    return ctx, ui_state


def run_interactive_ui(ctx: AppContext) -> AppContext:
    """
    Run the main interactive UI event loop.

    Args:
        ctx: Application context with config, tracks, and player state

    Returns:
        Updated AppContext after UI session ends
    """
    term = Terminal()

    with term.fullscreen(), term.cbreak(), term.hidden_cursor():
        try:
            ctx = main_loop(term, ctx)
        except KeyboardInterrupt:
            pass  # Cleanup already done in main_loop

    return ctx


def main_loop(term: Terminal, ctx: AppContext) -> AppContext:
    """
    Main event loop - functional style.

    Args:
        term: blessed Terminal instance
        ctx: Application context

    Returns:
        Updated AppContext after loop exits
    """
    # Create initial UI state (UI-only, not application state)
    # Load active library from database
    with database.get_db_connection() as conn:
        cursor = conn.execute("SELECT provider FROM active_library WHERE id = 1")
        row = cursor.fetchone()
        active_library = row["provider"] if row else "local"

    ui_state = UIState(active_library=active_library)

    # Thread-safe UIState updater for background tasks
    # Use RLock (reentrant lock) to allow same thread to acquire multiple times
    # This prevents deadlock when executor calls log() which calls update_ui_state_safe
    ui_state_lock = threading.RLock()

    def update_ui_state_safe(updates: dict):
        """Thread-safe UIState update from background threads."""
        nonlocal ui_state
        with ui_state_lock:
            # Session ID validation for comparison updates
            # Prevents race condition where old background thread overwrites new session
            if "comparison" in updates:
                new_comparison = updates["comparison"]
                current_comparison = ui_state.comparison

                logger.info(
                    f"🔍 update_ui_state_safe: comparing sessions - "
                    f"current(active={current_comparison.active}, session_id={current_comparison.session_id!r}, loading={current_comparison.loading}) vs "
                    f"new(active={new_comparison.active}, session_id={new_comparison.session_id!r}, loading={new_comparison.loading}, tracks={len(new_comparison.filtered_tracks)})"
                )

                # Rule 1: Block updates from different sessions (only if current is active)
                if (
                    hasattr(current_comparison, "active")
                    and current_comparison.active
                    and hasattr(new_comparison, "session_id")
                    and new_comparison.session_id
                    and hasattr(current_comparison, "session_id")
                    and current_comparison.session_id
                    and new_comparison.session_id != current_comparison.session_id
                ):
                    logger.warning(
                        f"❌ Ignoring stale comparison update (different session): "
                        f"current_session={current_comparison.session_id}, "
                        f"update_session={new_comparison.session_id}"
                    )
                    return  # Ignore this update

                # Rule 2: Never overwrite loaded state with loading state (same session)
                # This prevents executor from overwriting background thread's loaded data
                if (
                    hasattr(current_comparison, "loading")
                    and not current_comparison.loading
                    and hasattr(new_comparison, "loading")
                    and new_comparison.loading
                    and hasattr(current_comparison, "session_id")
                    and current_comparison.session_id
                    and hasattr(new_comparison, "session_id")
                    and new_comparison.session_id
                    and current_comparison.session_id == new_comparison.session_id
                ):
                    logger.warning(
                        f"❌ Ignoring loading state update (already loaded): "
                        f"session_id={current_comparison.session_id}"
                    )
                    return  # Ignore this update

            # Handle history_messages specially (add to history)
            if "history_messages" in updates:
                messages = updates.pop("history_messages")
                for text, color in messages:
                    ui_state = add_history_line(ui_state, text, color)

            # Replace state with updated fields
            ui_state = dataclasses.replace(ui_state, **updates)

    # Inject updater into context for background tasks
    ctx = dataclasses.replace(
        ctx, ui_mode="blessed", update_ui_state=update_ui_state_safe
    )

    # Enable blessed mode globally in log() function
    set_blessed_mode(update_ui_state_safe)

    # Initialize IPC server for external commands (hotkeys)
    command_queue = queue.Queue()
    response_queue = queue.Queue()
    ipc_srv = None

    if ctx.config.ipc.enabled if hasattr(ctx.config, "ipc") else True:
        try:
            ipc_srv = ipc_server.IPCServer(command_queue, response_queue)
            ipc_srv.start()
        except Exception as e:
            # IPC failure is non-fatal - continue without it
            ui_state = add_history_line(
                ui_state, f"⚠ IPC server failed to start: {e}", "yellow"
            )

    should_quit = False
    frame_count = 0
    last_state_hash = None
    needs_full_redraw = True
    last_input_text = ""
    last_palette_state = (
        False,  # palette_visible
        0,  # palette_selected
        False,  # confirmation_active
        False,  # wizard_active
        0,  # wizard_selected
        False,  # builder.active
        False,  # track_viewer_visible
        0,  # track_viewer_selected
        "main",  # track_viewer_mode
        False,  # analytics_viewer_visible
        0,  # analytics_viewer_scroll
        False,  # editor_visible
        0,  # editor_selected
        "main",  # editor_mode
        "",  # editor_input
        0,  # search_selected
        0,  # search_scroll
        "search",  # search_mode
        0,  # search_detail_scroll
        0,  # search_detail_selection
        False,  # comparison.active
        "a",  # comparison.highlighted
    )
    layout = None
    last_position = (
        0.0  # Track position separately for partial updates (float for smooth updates)
    )
    last_poll_time = time.time()  # Track when we last polled MPV for interpolation
    last_rendered_position = 0.0  # Track last rendered position for change detection
    dashboard_line_mapping = {}  # Store line offsets from last full dashboard render
    last_dashboard_height = None  # Track dashboard height to avoid unnecessary clears
    last_track_file = None  # Track previous track to detect changes
    startup_sync_started = False  # Track if we've started background sync

    try:
        while not should_quit:
            # Check for file changes if hot-reload is enabled
            _check_and_reload_files()

            # Detect track changes (immediate poll for instant metadata)
            current_track_file = ctx.player_state.current_track
            track_changed = current_track_file != last_track_file
            if track_changed:
                last_track_file = current_track_file

            # Poll player state at configured interval OR immediately on track change
            # For Spotify: poll every frame (uses internal cache, no API cost)
            # For MPV: poll every PLAYER_POLL_INTERVAL frames
            is_spotify = (
                ctx.player_state.current_track
                and ctx.player_state.current_track.startswith("spotify:")
            )
            should_poll_mpv = (frame_count % PLAYER_POLL_INTERVAL == 0) or track_changed
            should_poll = is_spotify or should_poll_mpv
            if should_poll:
                ctx, ui_state = poll_player_state(ctx, ui_state)
                # Update position tracking after poll for interpolation
                last_position = ctx.player_state.current_position
                last_poll_time = time.time()

            # Poll scan state at configured interval for smoother progress updates
            should_poll_scan = frame_count % SCAN_POLL_INTERVAL == 0
            if should_poll_scan:
                ui_state = poll_scan_state(ui_state)

            # Poll sync state at configured interval for smoother progress updates
            should_poll_sync = frame_count % SYNC_POLL_INTERVAL == 0
            if should_poll_sync:
                ui_state = poll_sync_state(ui_state)

            # Poll conversion state at configured interval for smoother progress updates
            should_poll_conversion = frame_count % CONVERSION_POLL_INTERVAL == 0
            if should_poll_conversion:
                ui_state = poll_conversion_state(ui_state)

            # Process IPC commands from external clients (hotkeys)
            try:
                while not command_queue.empty():
                    request_id, command, args = command_queue.get_nowait()

                    # Helper to add to history
                    def add_to_history(text):
                        nonlocal ui_state
                        # Use cyan color for IPC commands to distinguish them
                        ui_state = add_history_line(ui_state, text, "cyan")

                    # Process command
                    ctx, success, message = ipc_server.process_ipc_command(
                        ctx, command, args, add_to_history
                    )

                    # Send response back to IPC server
                    response_queue.put((request_id, success, message))

                    # Force full redraw after IPC command
                    needs_full_redraw = True
            except queue.Empty:
                pass
            except Exception as e:
                # Log IPC errors but don't crash UI
                ui_state = add_history_line(ui_state, f"⚠ IPC error: {e}", "yellow")

            # Check if state changed (only redraw if needed)
            # Only compute hash when we polled or when other state changes might have occurred
            # For Spotify: don't recompute hash every frame (we poll every frame for position updates)
            # Only recompute on MPV polls or scan polls
            current_state_hash = None
            should_recompute_hash = (
                should_poll_mpv or should_poll_scan or last_state_hash is None
            )

            if should_recompute_hash:
                # Hash excludes current_position to avoid full redraws every second
                # Position is tracked separately for partial dashboard updates
                # Include scan state for progress updates
                current_state_hash = hash(
                    (
                        ctx.player_state.current_track,
                        ctx.player_state.is_playing,
                        ctx.player_state.duration,
                        len(ui_state.history),
                        ui_state.feedback_message,
                        ui_state.scan_progress.is_scanning,
                        ui_state.scan_progress.files_scanned,
                        ui_state.scan_progress.phase,
                    )
                )

            # Check for input-only changes (no full redraw needed)
            input_changed = ui_state.input_text != last_input_text
            palette_state_changed = (
                ui_state.palette_visible,
                ui_state.palette_selected,
                ui_state.confirmation_active,
                ui_state.wizard_active,
                ui_state.wizard_selected,
                ui_state.builder.active,
                ui_state.track_viewer_visible,
                ui_state.track_viewer_selected,
                ui_state.track_viewer_mode,
                ui_state.analytics_viewer_visible,
                ui_state.analytics_viewer_scroll,
                ui_state.editor_visible,
                ui_state.editor_selected,
                ui_state.editor_mode,
                ui_state.editor_input,
                ui_state.search_selected,
                ui_state.search_scroll,
                ui_state.search_mode,
                ui_state.search_detail_scroll,
                ui_state.search_detail_selection,
                ui_state.comparison.active,
                ui_state.comparison.highlighted,  # Must match last_palette_state tuple
            ) != last_palette_state

            # Determine if we need a full redraw
            needs_full_redraw = needs_full_redraw or (
                current_state_hash is not None and current_state_hash != last_state_hash
            )

            # DEBUG: Log redraw decision
            logger.debug(f"Frame {frame_count}: needs_full_redraw={needs_full_redraw}, hash_changed={current_state_hash != last_state_hash if current_state_hash else 'N/A'}")

            if needs_full_redraw:
                # Render dashboard first to check if height changed (lock for thread safety)
                with ui_state_lock:
                    dashboard_height, dashboard_line_mapping = render_dashboard(
                        term,
                        ctx.player_state,
                        ui_state,
                        0,  # Dashboard always starts at y=0
                    )

                # Only clear screen if dashboard height changed or first render
                height_changed = last_dashboard_height != dashboard_height
                if height_changed or last_dashboard_height is None:
                    # Clear screen and re-render everything
                    print(term.clear)

                    # Re-render dashboard after clear
                    dashboard_height, dashboard_line_mapping = render_dashboard(
                        term, ctx.player_state, ui_state, 0
                    )

                # Update tracking variables
                last_state_hash = current_state_hash
                needs_full_redraw = False
                last_dashboard_height = dashboard_height

                # Calculate layout with actual dashboard height
                layout = calculate_layout(term, ui_state, dashboard_height)

                # Render remaining sections
                render_history(
                    term, ui_state, layout["history_y"], layout["history_height"]
                )

                render_input(term, ui_state, layout["input_y"])

                # Render palette, wizard, builder, track viewer, or comparison (mutually exclusive)
                if ui_state.comparison.active:
                    from music_minion.ui.blessed.components.comparison import (
                        render_comparison_overlay,
                    )

                    render_comparison_overlay(
                        term,
                        ui_state.comparison,
                        ctx.player_state,
                        layout,
                    )
                elif ui_state.wizard_active:
                    render_smart_playlist_wizard(
                        term, ui_state, layout["palette_y"], layout["palette_height"]
                    )
                elif ui_state.builder.active:
                    from music_minion.ui.blessed.components.playlist_builder import render_playlist_builder
                    render_playlist_builder(
                        term, ui_state, layout["palette_y"], layout["palette_height"]
                    )
                elif ui_state.palette_visible:
                    render_palette(
                        term, ui_state, layout["palette_y"], layout["palette_height"]
                    )
                elif ui_state.track_viewer_visible:
                    render_track_viewer(
                        term,
                        ui_state,
                        layout["track_viewer_y"],
                        layout["track_viewer_height"],
                    )
                elif ui_state.rating_history_visible:
                    render_rating_history_viewer(
                        term,
                        ui_state,
                        layout["palette_y"],  # Use palette area
                        layout["palette_height"],
                    )
                elif ui_state.comparison_history_visible:
                    render_comparison_history_viewer(
                        term,
                        ui_state,
                        layout["palette_y"],  # Use palette area
                        layout["palette_height"],
                    )
                elif ui_state.analytics_viewer_visible:
                    render_analytics_viewer(
                        term,
                        ui_state,
                        layout["analytics_viewer_y"],
                        layout["analytics_viewer_height"],
                    )
                elif ui_state.editor_visible:
                    render_metadata_editor(
                        term,
                        ui_state,
                        layout["palette_y"],  # Use palette area
                        layout["palette_height"],
                    )

                # Flush output
                sys.stdout.flush()

                last_input_text = ui_state.input_text
                last_palette_state = (
                    ui_state.palette_visible,
                    ui_state.palette_selected,
                    ui_state.confirmation_active,
                    ui_state.wizard_active,
                    ui_state.wizard_selected,
                    ui_state.builder.active,
                    ui_state.track_viewer_visible,
                    ui_state.track_viewer_selected,
                    ui_state.track_viewer_mode,
                    ui_state.analytics_viewer_visible,
                    ui_state.analytics_viewer_scroll,
                    ui_state.editor_visible,
                    ui_state.editor_selected,
                    ui_state.editor_mode,
                    ui_state.editor_input,
                    ui_state.search_selected,
                    ui_state.search_scroll,
                    ui_state.search_mode,
                    ui_state.search_detail_scroll,
                    ui_state.search_detail_selection,
                    ui_state.comparison.active,
                    ui_state.comparison.highlighted,  # Track highlighted track changes
                )

                # Update rendered position for partial update threshold
                last_rendered_position = ctx.player_state.current_position

                # Start background sync after first render (instant UI)
                if not startup_sync_started:
                    startup_sync_started = True
                    ui_state = add_history_line(
                        ui_state, "🔄 Starting background sync...", "cyan"
                    )
                    logger.info("Starting background sync after UI render")

                    def _background_sync_worker():
                        """Background thread for context-aware sync."""
                        nonlocal ctx

                        # Suppress stdout printing from log() calls (prevents UI interference)
                        threading.current_thread().silent_logging = True

                        try:
                            from music_minion.commands import sync

                            # Capture current player state before sync
                            current_player_state = ctx.player_state
                            current_spotify_player = ctx.spotify_player

                            # Run sync (updates tracks but may lose player state)
                            updated_ctx, _ = sync.handle_sync_command(ctx)

                            # Preserve current player state (prevent clearing current track)
                            ctx = dataclasses.replace(
                                updated_ctx,
                                player_state=current_player_state,
                                spotify_player=current_spotify_player,
                            )

                            # Update UI state from background thread
                            if ctx.update_ui_state:
                                ctx.update_ui_state(
                                    {
                                        "history_messages": [
                                            ("✅ Auto-sync complete", "green")
                                        ]
                                    }
                                )
                        except Exception as e:
                            logger.exception(f"Background sync failed: {e}")
                            if ctx.update_ui_state:
                                ctx.update_ui_state(
                                    {
                                        "history_messages": [
                                            (f"⚠ Auto-sync failed: {e}", "yellow")
                                        ]
                                    }
                                )
                        finally:
                            # Always clear the flag
                            threading.current_thread().silent_logging = False

                    # Start background thread
                    sync_thread = threading.Thread(
                        target=_background_sync_worker,
                        daemon=True,
                        name="StartupSyncThread",
                    )
                    sync_thread.start()

            # Check if modal visibility changed (requires full redraw)
            if palette_state_changed and (
                ui_state.palette_visible != last_palette_state[0]
                or ui_state.wizard_active != last_palette_state[3]
                or ui_state.builder.active != last_palette_state[5]
                or ui_state.track_viewer_visible != last_palette_state[6]
                or ui_state.track_viewer_mode != last_palette_state[8]
                or ui_state.analytics_viewer_visible != last_palette_state[9]
                or ui_state.editor_visible != last_palette_state[11]
                or ui_state.comparison.active
                != last_palette_state[20]  # Check comparison state
            ):
                needs_full_redraw = True

            # DEBUG: Log input/palette state
            logger.debug(f"Frame {frame_count}: input_changed={input_changed}, palette_state_changed={palette_state_changed}")
            if input_changed or palette_state_changed:
                # Partial update - only input and palette changed
                if layout and not needs_full_redraw:
                    # Clear input area (3 lines: top border, input, bottom border)
                    input_y = layout["input_y"]
                    for i in range(3):
                        write_at(term, 0, input_y + i, "")

                    # Clear palette/wizard/builder/track viewer/analytics viewer/editor/comparison area if visible
                    if (
                        ui_state.palette_visible
                        or ui_state.wizard_active
                        or ui_state.builder.active
                        or ui_state.track_viewer_visible
                        or ui_state.analytics_viewer_visible
                        or ui_state.editor_visible
                        or ui_state.comparison.active
                    ):
                        overlay_y = layout[
                            "palette_y"
                        ]  # Same position for all overlays
                        overlay_height = layout["palette_height"]
                        for i in range(overlay_height):
                            sys.stdout.write(
                                term.move_xy(0, overlay_y + i) + term.clear_eol
                            )

                    # Re-render
                    render_input(term, ui_state, layout["input_y"])

                    # Render palette, wizard, builder, track viewer, analytics viewer, or comparison (mutually exclusive)
                    if ui_state.comparison.active:
                        from music_minion.ui.blessed.components.comparison import (
                            render_comparison_overlay,
                        )

                        render_comparison_overlay(
                            term,
                            ui_state.comparison,
                            ctx.player_state,
                            layout,
                        )
                    elif ui_state.wizard_active:
                        render_smart_playlist_wizard(
                            term,
                            ui_state,
                            layout["palette_y"],
                            layout["palette_height"],
                        )
                    elif ui_state.builder.active:
                        from music_minion.ui.blessed.components.playlist_builder import render_playlist_builder
                        render_playlist_builder(
                            term, ui_state, layout["palette_y"], layout["palette_height"]
                        )
                    elif ui_state.palette_visible:
                        render_palette(
                            term,
                            ui_state,
                            layout["palette_y"],
                            layout["palette_height"],
                        )
                    elif ui_state.track_viewer_visible:
                        render_track_viewer(
                            term,
                            ui_state,
                            layout["track_viewer_y"],
                            layout["track_viewer_height"],
                        )
                    elif ui_state.rating_history_visible:
                        render_rating_history_viewer(
                            term,
                            ui_state,
                            layout["palette_y"],
                            layout["palette_height"],
                        )
                    elif ui_state.comparison_history_visible:
                        render_comparison_history_viewer(
                            term,
                            ui_state,
                            layout["palette_y"],
                            layout["palette_height"],
                        )
                    elif ui_state.analytics_viewer_visible:
                        render_analytics_viewer(
                            term,
                            ui_state,
                            layout["analytics_viewer_y"],
                            layout["analytics_viewer_height"],
                        )
                    elif ui_state.editor_visible:
                        render_metadata_editor(
                            term,
                            ui_state,
                            layout["palette_y"],
                            layout["palette_height"],
                        )

                    # Flush output
                    sys.stdout.flush()

                    last_input_text = ui_state.input_text
                    last_palette_state = (
                        ui_state.palette_visible,
                        ui_state.palette_selected,
                        ui_state.confirmation_active,
                        ui_state.wizard_active,
                        ui_state.wizard_selected,
                        ui_state.builder.active,
                        ui_state.track_viewer_visible,
                        ui_state.track_viewer_selected,
                        ui_state.track_viewer_mode,
                        ui_state.analytics_viewer_visible,
                        ui_state.analytics_viewer_scroll,
                        ui_state.editor_visible,
                        ui_state.editor_selected,
                        ui_state.editor_mode,
                        ui_state.editor_input,
                        ui_state.search_selected,
                        ui_state.search_scroll,
                        ui_state.search_mode,
                        ui_state.search_detail_scroll,
                        ui_state.search_detail_selection,
                        ui_state.comparison.active,
                        ui_state.comparison.highlighted,  # Track highlighted track changes
                    )

            else:
                # Only check for position updates if we have a track and layout
                # DEBUG: Log that we reached the else branch
                logger.debug(f"Partial update branch: track={bool(ctx.player_state.current_track)}, layout={bool(layout)}, mapping={bool(dashboard_line_mapping)}")
                if ctx.player_state.current_track and layout and dashboard_line_mapping:
                    # Use position directly from player state
                    # For Spotify: already interpolated by SpotifyPlayer (polled every frame)
                    # For MPV: interpolated here for smooth updates between polls
                    is_spotify_track = (
                        ctx.player_state.current_track
                        and ctx.player_state.current_track.startswith("spotify:")
                    )

                    if is_spotify_track:
                        # Use SpotifyPlayer's cached position directly (already interpolated)
                        current_position = ctx.player_state.current_position
                    else:
                        # For MPV: calculate interpolated position for smooth updates between polls
                        time_since_poll = time.time() - last_poll_time
                        current_position = last_position + time_since_poll

                    # Check if position crossed threshold
                    position_changed = (
                        abs(current_position - last_rendered_position)
                        >= POSITION_UPDATE_THRESHOLD
                    )
                    # DEBUG: Log position comparison
                    logger.debug(f"Position check: current={current_position:.2f}, last_rendered={last_rendered_position:.2f}, changed={position_changed}")

                    if position_changed:
                        # Partial update - only update time-sensitive dashboard elements
                        from .components.dashboard import render_dashboard_partial

                        # DEBUG: Log partial render call
                        logger.debug(f"Calling render_dashboard_partial at y={layout['dashboard_y']}")

                        # Use current position for smooth visual updates
                        display_state = ctx.player_state._replace(
                            current_position=current_position
                        )

                        render_dashboard_partial(
                            term,
                            display_state,
                            ui_state,
                            layout["dashboard_y"],
                            dashboard_line_mapping,
                        )

                        sys.stdout.flush()
                        last_rendered_position = current_position

            # Wait for input (with timeout for background updates)
            key = term.inkey(timeout=0.1)

            if key:
                # Handle keyboard input
                palette_height = layout["palette_height"] if layout else 10
                analytics_viewer_height = (
                    layout["analytics_viewer_height"] if layout else 30
                )
                ui_state, command_line = handle_key(
                    ui_state, key, palette_height, analytics_viewer_height
                )

                # Execute command if one was triggered
                if command_line:
                    with ui_state_lock:
                        ctx, ui_state, should_quit = execute_command(
                            ctx, ui_state, command_line
                        )
                    # Full redraw after command execution
                    needs_full_redraw = True
                    # Reset interpolation baseline to new position (critical for seek commands)
                    last_position = ctx.player_state.current_position
                    last_poll_time = time.time()

            frame_count += 1
    except KeyboardInterrupt:
        # Cleanup BEFORE propagating exception
        logger.info("Ctrl+C detected - cleaning up")
        if ctx.player_state.playback_source == "spotify" and ctx.spotify_player:
            try:
                ctx.spotify_player.pause()
                logger.info("Paused Spotify playback on exit")
            except Exception as e:
                logger.exception(f"Failed to pause Spotify: {e}")
        # Re-raise to let outer handlers know we're exiting
        raise

    # Cleanup: Stop IPC server
    if ipc_srv:
        try:
            ipc_srv.stop()
        except Exception:
            pass  # Silently ignore cleanup errors

    # Restore normal logging mode (CLI)
    clear_blessed_mode()

    return ctx
