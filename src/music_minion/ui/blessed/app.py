"""Main event loop and entry point for blessed UI."""

import sys
import time
import threading
import dataclasses
import queue
from pathlib import Path
from blessed import Terminal
from loguru import logger

from music_minion.context import AppContext
from music_minion.commands import admin
from music_minion.core import database
from music_minion.ipc import server as ipc_server
from .state import UIState, PlaylistInfo, update_track_info, add_history_line
from .components import (
    render_dashboard,
    render_history,
    render_input,
    render_palette,
    render_smart_playlist_wizard,
    calculate_layout,
    render_analytics_viewer,
)
from .components.track_viewer import render_track_viewer
from .components.metadata_editor import render_metadata_editor
from .events.keyboard import handle_key
from .events.commands import execute_command

# Frame interval constants for background updates
PLAYER_POLL_INTERVAL = 10  # Poll MPV every 10 frames (~1 second)
SCAN_POLL_INTERVAL = 5  # Poll scan progress every 5 frames (~0.5 seconds)
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
    from .state import update_scan_progress, end_scan, add_history_line

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
        files_scanned=scan_state.get('files_scanned', 0),
        current_file=scan_state.get('current_file', ''),
        phase=scan_state.get('phase', 'scanning')
    )

    # Start scan UI if not already showing
    if not ui_state.scan_progress.is_scanning:
        from .state import start_scan
        ui_state = start_scan(ui_state, scan_state.get('total_files', 0))

    # Update total files if changed
    if scan_state.get('total_files', 0) != ui_state.scan_progress.total_files:
        ui_state = replace(
            ui_state,
            scan_progress=replace(
                ui_state.scan_progress,
                total_files=scan_state.get('total_files', 0)
            )
        )

    # Check if scan completed
    if scan_state.get('completed', False):
        # End scan UI
        ui_state = end_scan(ui_state)

        # Show results in history
        if scan_state.get('error'):
            ui_state = add_history_line(ui_state, f"❌ Scan failed: {scan_state['error']}", 'red')
        else:
            tracks = scan_state.get('tracks', [])
            added = scan_state.get('added', 0)
            updated = scan_state.get('updated', 0)
            errors = scan_state.get('errors', 0)
            stats = scan_state.get('stats', {})

            ui_state = add_history_line(ui_state, "✅ Scan complete!", 'green')
            ui_state = add_history_line(ui_state, f"  📝 New tracks: {added}", 'white')
            ui_state = add_history_line(ui_state, f"  🔄 Updated tracks: {updated}", 'white')
            if errors:
                ui_state = add_history_line(ui_state, f"  ⚠️  Errors: {errors}", 'yellow')

            if stats:
                ui_state = add_history_line(ui_state, "", 'white')
                ui_state = add_history_line(ui_state, "📚 Library Overview:", 'cyan')
                ui_state = add_history_line(ui_state, f"  Total duration: {stats.get('total_duration_str', 'N/A')}", 'white')
                ui_state = add_history_line(ui_state, f"  Total size: {stats.get('total_size_str', 'N/A')}", 'white')
                ui_state = add_history_line(ui_state, f"  Artists: {stats.get('artists', 0)}", 'white')
                ui_state = add_history_line(ui_state, f"  Albums: {stats.get('albums', 0)}", 'white')

        # Clear scan state so completion messages don't repeat on next poll
        admin._clear_scan_state()

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
    from ...core import database
    from ...domain.playback import player, state as playback_state
    from ...domain.playlists import crud as playlists
    from ...commands.playback import get_available_tracks, get_next_track, play_track

    # Get player status
    try:
        status = player.get_player_status(ctx.player_state)

        # Update player state in AppContext
        new_player_state = ctx.player_state._replace(
            current_track=status.get('file'),
            is_playing=status.get('playing', False),
            current_position=status.get('position', 0.0),
            duration=status.get('duration', 0.0),
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
                    ui_state = add_history_line(ui_state, f"♪ Now playing: {library.get_display_name(track)}", 'cyan')
                    if track.duration:
                        ui_state = add_history_line(ui_state, f"   Duration: {library.get_duration_str(track)}", 'blue')

                    dj_info = library.get_dj_info(track)
                    if dj_info != "No DJ metadata":
                        ui_state = add_history_line(ui_state, f"   {dj_info}", 'magenta')

        # If track changed, re-query player status to get new track info
        if track_changed:
            status = player.get_player_status(ctx.player_state)
            new_player_state = ctx.player_state._replace(
                current_track=status.get('file'),
                is_playing=status.get('playing', False),
                current_position=status.get('position', 0.0),
                duration=status.get('duration', 0.0),
            )
            ctx = ctx.with_player_state(new_player_state)

        # If we have a current track, fetch metadata for UI display
        current_file = status.get('file')
        if current_file:
            # Get track from database (handle both local paths and stream URLs)
            db_track = None

            # Check if current_file is a stream URL (contains api.soundcloud.com, youtube.com, etc.)
            if 'api.soundcloud.com/tracks/' in current_file:
                # Extract SoundCloud track ID from URL
                # Format: https://api.soundcloud.com/tracks/{id}/stream?oauth_token=...
                import re
                match = re.search(r'/tracks/(\d+)', current_file)
                if match:
                    soundcloud_id = match.group(1)
                    db_track = database.get_track_by_provider_id('soundcloud', soundcloud_id)
            elif 'youtube.com/watch' in current_file or 'youtu.be/' in current_file:
                # Extract YouTube video ID
                import re
                match = re.search(r'(?:v=|youtu\.be/)([a-zA-Z0-9_-]+)', current_file)
                if match:
                    youtube_id = match.group(1)
                    db_track = database.get_track_by_provider_id('youtube', youtube_id)
            else:
                # Assume local file path
                db_track = database.get_track_by_path(current_file)

            if db_track:
                # Build track data for UI display
                track_data = {
                    'title': db_track.get('title') or 'Unknown',
                    'artist': db_track.get('artist') or 'Unknown',
                    'remix_artist': db_track.get('remix_artist'),
                    'album': db_track.get('album'),
                    'year': db_track.get('year'),
                    'genre': db_track.get('genre'),
                    'bpm': db_track.get('bpm'),
                    'key': db_track.get('key'),
                }

                # Get additional database info
                tags = database.get_track_tags(db_track['id'])
                notes = database.get_track_notes(db_track['id'])

                track_data.update({
                    'tags': [t['tag_name'] for t in tags],
                    'notes': notes[0]['note_text'] if notes else '',
                    'rating': db_track.get('rating'),
                    'last_played': db_track.get('last_played'),
                    'play_count': db_track.get('play_count', 0),
                })

                ui_state = update_track_info(ui_state, track_data)

                # Check if track has SoundCloud like marker (for heart indicator)
                has_sc_like = database.has_soundcloud_like(db_track['id'])
                ui_state = replace(ui_state, current_track_has_soundcloud_like=has_sc_like)
            else:
                # Track not in database - clear metadata to show fallback
                ui_state = replace(ui_state, track_metadata=None, track_db_info=None, current_track_has_soundcloud_like=False)
        else:
            # No track playing - clear metadata
            ui_state = replace(ui_state, track_metadata=None, track_db_info=None, current_track_has_soundcloud_like=False)

        # Update shuffle mode state from database
        shuffle_enabled = playback_state.get_shuffle_mode()
        ui_state = replace(ui_state, shuffle_enabled=shuffle_enabled)

        # Update playlist info from database
        active = playlists.get_active_playlist()
        if active:
            playlist_tracks = playlists.get_playlist_tracks(active['id'])
            position_info = playback_state.get_playlist_position(active['id'])

            playlist_info = PlaylistInfo(
                id=active['id'],
                name=active['name'],
                type=active['type'],
                track_count=len(playlist_tracks),
                current_position=position_info[1] if position_info else None
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
            # Clean exit on Ctrl+C
            pass

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
        active_library = row['provider'] if row else 'local'

    ui_state = UIState(active_library=active_library)

    # Thread-safe UIState updater for background tasks
    ui_state_lock = threading.Lock()

    def update_ui_state_safe(updates: dict):
        """Thread-safe UIState update from background threads."""
        nonlocal ui_state
        with ui_state_lock:
            # Handle history_messages specially (add to history)
            if 'history_messages' in updates:
                messages = updates.pop('history_messages')
                for text, color in messages:
                    ui_state = add_history_line(ui_state, text, color)

            # Replace state with updated fields
            ui_state = dataclasses.replace(ui_state, **updates)

    # Inject updater into context for background tasks
    ctx = dataclasses.replace(ctx,
        ui_mode='blessed',
        update_ui_state=update_ui_state_safe
    )

    # Auto-sync on startup (fast incremental sync)
    logger.info("Running auto-sync on startup...")
    try:
        from music_minion.commands import sync
        ctx, _ = sync.handle_sync_command(ctx)
        ui_state = add_history_line(ui_state, "✓ Auto-sync complete", 'green')
    except Exception as e:
        logger.exception(f"Auto-sync failed: {e}")
        # Continue even if sync fails (non-critical)
        ui_state = add_history_line(ui_state, f"⚠ Auto-sync failed: {e}", 'yellow')

    # Initialize IPC server for external commands (hotkeys)
    command_queue = queue.Queue()
    response_queue = queue.Queue()
    ipc_srv = None

    if ctx.config.ipc.enabled if hasattr(ctx.config, 'ipc') else True:
        try:
            ipc_srv = ipc_server.IPCServer(command_queue, response_queue)
            ipc_srv.start()
        except Exception as e:
            # IPC failure is non-fatal - continue without it
            ui_state = add_history_line(ui_state, f"⚠ IPC server failed to start: {e}", 'yellow')

    should_quit = False
    frame_count = 0
    last_state_hash = None
    needs_full_redraw = True
    last_input_text = ""
    last_palette_state = (False, 0, False, False, 0, False, 0, False, 0, False, 0, 'main', '', 0, 0, 'search', 0, 0)  # (palette_visible, palette_selected, confirmation_active, wizard_active, wizard_selected, track_viewer_visible, track_viewer_selected, analytics_viewer_visible, analytics_viewer_scroll, editor_visible, editor_selected, editor_mode, editor_input, search_selected, search_scroll, search_mode, search_detail_scroll, search_detail_selection)
    layout = None
    last_position = 0.0  # Track position separately for partial updates (float for smooth updates)
    last_poll_time = time.time()  # Track when we last polled MPV for interpolation
    last_rendered_position = 0.0  # Track last rendered position for change detection
    dashboard_line_mapping = {}  # Store line offsets from last full dashboard render
    last_dashboard_height = None  # Track dashboard height to avoid unnecessary clears
    last_track_file = None  # Track previous track to detect changes

    while not should_quit:
        # Check for file changes if hot-reload is enabled
        _check_and_reload_files()

        # Detect track changes (immediate poll for instant metadata)
        current_track_file = ctx.player_state.current_track
        track_changed = (current_track_file != last_track_file)
        if track_changed:
            last_track_file = current_track_file

        # Poll player state at configured interval OR immediately on track change
        should_poll = (frame_count % PLAYER_POLL_INTERVAL == 0) or track_changed
        if should_poll:
            ctx, ui_state = poll_player_state(ctx, ui_state)

        # Poll scan state at configured interval for smoother progress updates
        should_poll_scan = frame_count % SCAN_POLL_INTERVAL == 0
        if should_poll_scan:
            ui_state = poll_scan_state(ui_state)

        # Process IPC commands from external clients (hotkeys)
        try:
            while not command_queue.empty():
                request_id, command, args = command_queue.get_nowait()

                # Helper to add to history
                def add_to_history(text):
                    nonlocal ui_state
                    # Use cyan color for IPC commands to distinguish them
                    ui_state = add_history_line(ui_state, text, 'cyan')

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
            ui_state = add_history_line(ui_state, f"⚠ IPC error: {e}", 'yellow')

        # Check if state changed (only redraw if needed)
        # Only compute hash when we polled or when other state changes might have occurred
        current_state_hash = None
        if should_poll or should_poll_scan or last_state_hash is None:
            # Hash excludes current_position to avoid full redraws every second
            # Position is tracked separately for partial dashboard updates
            # Include scan state for progress updates
            current_state_hash = hash((
                ctx.player_state.current_track,
                ctx.player_state.is_playing,
                ctx.player_state.duration,
                len(ui_state.history),
                ui_state.feedback_message,
                ui_state.scan_progress.is_scanning,
                ui_state.scan_progress.files_scanned,
                ui_state.scan_progress.phase,
                ui_state.sync_active,
                ui_state.sync_progress,
                ui_state.sync_current_name,
            ))

        # Check for input-only changes (no full redraw needed)
        input_changed = ui_state.input_text != last_input_text
        palette_state_changed = (ui_state.palette_visible, ui_state.palette_selected, ui_state.confirmation_active, ui_state.wizard_active, ui_state.wizard_selected, ui_state.track_viewer_visible, ui_state.track_viewer_selected, ui_state.analytics_viewer_visible, ui_state.analytics_viewer_scroll, ui_state.editor_visible, ui_state.editor_selected, ui_state.editor_mode, ui_state.editor_input, ui_state.search_selected, ui_state.search_scroll, ui_state.search_mode, ui_state.search_detail_scroll, ui_state.search_detail_selection) != last_palette_state

        # Determine if we need a full redraw
        needs_full_redraw = needs_full_redraw or (current_state_hash is not None and current_state_hash != last_state_hash)

        if needs_full_redraw:
            # Render dashboard first to check if height changed (lock for thread safety)
            with ui_state_lock:
                dashboard_height, dashboard_line_mapping = render_dashboard(
                    term,
                    ctx.player_state,
                    ui_state,
                    0  # Dashboard always starts at y=0
                )

            # Only clear screen if dashboard height changed or first render
            height_changed = last_dashboard_height != dashboard_height
            if height_changed or last_dashboard_height is None:
                # Clear screen and re-render everything
                print(term.clear)

                # Re-render dashboard after clear
                dashboard_height, dashboard_line_mapping = render_dashboard(
                    term,
                    ctx.player_state,
                    ui_state,
                    0
                )

            # Update tracking variables
            last_state_hash = current_state_hash
            needs_full_redraw = False
            last_dashboard_height = dashboard_height

            # Calculate layout with actual dashboard height
            layout = calculate_layout(term, ui_state, dashboard_height)

            # Render remaining sections
            render_history(
                term,
                ui_state,
                layout['history_y'],
                layout['history_height']
            )

            render_input(
                term,
                ui_state,
                layout['input_y']
            )

            # Render palette, wizard, or track viewer (mutually exclusive)
            if ui_state.wizard_active:
                render_smart_playlist_wizard(
                    term,
                    ui_state,
                    layout['palette_y'],
                    layout['palette_height']
                )
            elif ui_state.palette_visible:
                render_palette(
                    term,
                    ui_state,
                    layout['palette_y'],
                    layout['palette_height']
                )
            elif ui_state.track_viewer_visible:
                render_track_viewer(
                    term,
                    ui_state,
                    layout['track_viewer_y'],
                    layout['track_viewer_height']
                )
            elif ui_state.analytics_viewer_visible:
                render_analytics_viewer(
                    term,
                    ui_state,
                    layout['analytics_viewer_y'],
                    layout['analytics_viewer_height']
                )
            elif ui_state.editor_visible:
                render_metadata_editor(
                    term,
                    ui_state,
                    layout['palette_y'],  # Use palette area
                    layout['palette_height']
                )

            # Flush output
            sys.stdout.flush()

            last_input_text = ui_state.input_text
            last_palette_state = (ui_state.palette_visible, ui_state.palette_selected, ui_state.confirmation_active, ui_state.wizard_active, ui_state.wizard_selected, ui_state.track_viewer_visible, ui_state.track_viewer_selected, ui_state.analytics_viewer_visible, ui_state.analytics_viewer_scroll, ui_state.editor_visible, ui_state.editor_selected, ui_state.editor_mode, ui_state.editor_input, ui_state.search_selected, ui_state.search_scroll, ui_state.search_mode, ui_state.search_detail_scroll, ui_state.search_detail_selection)

            # Update position tracking atomically after full redraw
            last_position = ctx.player_state.current_position
            last_poll_time = time.time()
            last_rendered_position = ctx.player_state.current_position

        # Check if modal visibility changed (requires full redraw)
        if palette_state_changed and (ui_state.palette_visible != last_palette_state[0] or ui_state.wizard_active != last_palette_state[3] or ui_state.track_viewer_visible != last_palette_state[5] or ui_state.analytics_viewer_visible != last_palette_state[7] or ui_state.editor_visible != last_palette_state[9]):
            needs_full_redraw = True

        if input_changed or palette_state_changed:
            # Partial update - only input and palette changed
            if layout and not needs_full_redraw:
                # Clear input area (3 lines: top border, input, bottom border)
                input_y = layout['input_y']
                for i in range(3):
                    sys.stdout.write(term.move_xy(0, input_y + i) + term.clear_eol)

                # Clear palette/wizard/track viewer/analytics viewer/editor area if visible
                if ui_state.palette_visible or ui_state.wizard_active or ui_state.track_viewer_visible or ui_state.analytics_viewer_visible or ui_state.editor_visible:
                    overlay_y = layout['palette_y']  # Same position for all overlays
                    overlay_height = layout['palette_height']
                    for i in range(overlay_height):
                        sys.stdout.write(term.move_xy(0, overlay_y + i) + term.clear_eol)

                # Re-render
                render_input(
                    term,
                    ui_state,
                    layout['input_y']
                )

                # Render palette, wizard, track viewer, or analytics viewer (mutually exclusive)
                if ui_state.wizard_active:
                    render_smart_playlist_wizard(
                        term,
                        ui_state,
                        layout['palette_y'],
                        layout['palette_height']
                    )
                elif ui_state.palette_visible:
                    render_palette(
                        term,
                        ui_state,
                        layout['palette_y'],
                        layout['palette_height']
                    )
                elif ui_state.track_viewer_visible:
                    render_track_viewer(
                        term,
                        ui_state,
                        layout['track_viewer_y'],
                        layout['track_viewer_height']
                    )
                elif ui_state.analytics_viewer_visible:
                    render_analytics_viewer(
                        term,
                        ui_state,
                        layout['analytics_viewer_y'],
                        layout['analytics_viewer_height']
                    )
                elif ui_state.editor_visible:
                    render_metadata_editor(
                        term,
                        ui_state,
                        layout['palette_y'],
                        layout['palette_height']
                    )

                # Flush output
                sys.stdout.flush()

                last_input_text = ui_state.input_text
                last_palette_state = (ui_state.palette_visible, ui_state.palette_selected, ui_state.confirmation_active, ui_state.wizard_active, ui_state.wizard_selected, ui_state.track_viewer_visible, ui_state.track_viewer_selected, ui_state.analytics_viewer_visible, ui_state.analytics_viewer_scroll, ui_state.editor_visible, ui_state.editor_selected, ui_state.editor_mode, ui_state.editor_input, ui_state.search_selected, ui_state.search_scroll, ui_state.search_mode, ui_state.search_detail_scroll, ui_state.search_detail_selection)

        else:
            # Only check for position updates if playing and we have layout
            if ctx.player_state.is_playing and layout and dashboard_line_mapping:
                # Calculate interpolated position for smooth updates between MPV polls
                # This gives sub-second visual updates without extra MPV queries
                time_since_poll = time.time() - last_poll_time
                interpolated_position = last_position + time_since_poll

                # Check if interpolated position crossed threshold
                position_changed = abs(interpolated_position - last_rendered_position) >= POSITION_UPDATE_THRESHOLD

                if position_changed:
                    # Partial update - only update time-sensitive dashboard elements
                    # Create temporary player state with interpolated position for rendering
                    from .components.dashboard import render_dashboard_partial

                    # Use interpolated position for smooth visual updates
                    display_state = ctx.player_state._replace(current_position=interpolated_position)

                    render_dashboard_partial(
                        term,
                        display_state,
                        ui_state,
                        layout['dashboard_y'],
                        dashboard_line_mapping
                    )

                    sys.stdout.flush()
                    last_rendered_position = interpolated_position

        # Wait for input (with timeout for background updates)
        key = term.inkey(timeout=0.1)

        if key:
            # Handle keyboard input
            palette_height = layout['palette_height'] if layout else 10
            analytics_viewer_height = layout['analytics_viewer_height'] if layout else 30
            ui_state, command_line = handle_key(ui_state, key, palette_height, analytics_viewer_height)

            # Execute command if one was triggered
            if command_line:
                ctx, ui_state, should_quit = execute_command(ctx, ui_state, command_line)
                # Full redraw after command execution
                needs_full_redraw = True

        frame_count += 1

    # Cleanup: Stop IPC server
    if ipc_srv:
        try:
            ipc_srv.stop()
        except Exception:
            pass  # Silently ignore cleanup errors

    return ctx
