"""
Music Minion CLI - Main entry point and interactive loop
"""

import sys
import threading
import time
from pathlib import Path
from typing import List, Optional

from loguru import logger

from music_minion.core import config
from music_minion.core import database
from music_minion.core.output import setup_loguru
from music_minion.domain import library
from music_minion.domain import playback
from music_minion.domain import ai
from music_minion import ui
from music_minion.domain import playlists
from music_minion.domain import sync
from music_minion import command_palette
from music_minion import router
from music_minion.helpers import (
    cleanup_web_processes_safe,
    cleanup_file_watcher_safe,
)
from music_minion import helpers
from music_minion.utils import parsers

# Global state for interactive mode
current_player_state: playback.PlayerState = playback.PlayerState()
music_tracks: List[library.Track] = []
current_config: config.Config = config.Config()

# Global hot-reload state (when --dev flag is used)
file_watcher_observer = None
file_watcher_handler = None

# Global console for Rich output
try:
    from rich.console import Console

    console = Console()
except ImportError:
    # Fallback if Rich is not available
    console = None


def safe_print(message: str, style: str = None) -> None:
    """Print using Rich Console if available, otherwise fallback to regular print."""
    if console:
        if style:
            console.print(message, style=style)
        else:
            console.print(message)
    else:
        print(message)


def _auto_sync_background(cfg: config.Config) -> None:
    """Background thread function for auto-sync on startup.

    Runs sync_import silently in the background without blocking UI startup.
    Any errors are caught and logged without interrupting the main thread.
    """
    try:
        sync.sync_import(cfg, force_all=False, show_progress=False)
    except Exception as e:
        logger.exception("Background sync failed")


def interactive_mode_with_dashboard() -> None:
    """Run the interactive command loop with fixed top dashboard and scrolling commands."""
    import time
    import signal
    import threading
    import os
    from rich.console import Console

    global current_config

    # Run database migrations on startup
    database.init_database()

    # Auto-sync on startup if enabled (run in background thread)
    if current_config.sync.auto_sync_on_startup:
        print("🔄 Starting background sync...")
        sync_thread = threading.Thread(
            target=_auto_sync_background,
            args=(current_config,),
            daemon=True,
            name="AutoSyncThread",
        )
        sync_thread.start()

    console = Console()

    # Pass config to UI module
    ui.set_ui_config(current_config.ui)

    # Clear session state
    ui.clear_session()

    # Shared state for dashboard updates
    dashboard_state = {
        "should_update": True,
        "running": True,
        "last_track": None,
        "dashboard_content": None,
    }

    def get_current_track_metadata():
        """Get metadata for the current track."""
        global current_player_state, music_tracks

        if not current_player_state.current_track:
            return None

        # Find track in library
        track = None
        for t in music_tracks:
            if str(t.local_path) == current_player_state.current_track:
                track = t
                break

        if not track:
            return None

        # Get metadata
        metadata = {
            "title": track.title or "Unknown",
            "artist": track.artist or "Unknown",
            "album": track.album,
            "year": track.year,
            "genre": track.genre,
            "bpm": track.bpm,
            "key": track.key,
        }

        return metadata

    def get_current_track_db_info():
        """Get database info for current track."""
        global current_player_state

        if not current_player_state.current_track:
            return None

        try:
            # Find track in library first to get metadata
            track = None
            for t in music_tracks:
                if str(t.local_path) == current_player_state.current_track:
                    track = t
                    break

            if not track:
                return None

            # Get track ID from database
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

            # Get tags
            tags_data = database.get_track_tags(track_id)
            tags = [t["tag_name"] for t in tags_data if not t.get("blacklisted", False)]

            # Get latest rating
            ratings = database.get_track_ratings(track_id)
            latest_rating = None
            if ratings:
                # Convert rating type to numeric score
                rating_map = {"archive": 0, "skip": 25, "like": 60, "love": 85}
                latest_rating = rating_map.get(ratings[0]["rating_type"], 50)

            # Get notes
            notes_data = database.get_track_notes(track_id)
            latest_note = notes_data[0]["note"] if notes_data else ""

            # Get play stats
            play_count = len(ratings)
            last_played = ratings[0]["created_at"] if ratings else None

            return {
                "tags": tags,
                "notes": latest_note,
                "rating": latest_rating,
                "last_played": last_played,
                "play_count": play_count,
            }
        except:
            return None

    def dashboard_updater():
        """Background thread to update dashboard in real-time."""
        last_update_time = time.time()
        last_terminal_size = None

        while dashboard_state["running"]:
            try:
                current_time = time.time()

                # Check for track completion using context
                ctx = helpers.create_context_from_globals()
                ctx = helpers.check_and_handle_track_completion(ctx)
                helpers.sync_context_to_globals(ctx)

                # Update player state
                if ctx.player_state.process:
                    new_state = playback.update_player_status(ctx.player_state)
                    ctx = ctx.with_player_state(new_state)
                    helpers.sync_context_to_globals(ctx)

                # Check if terminal was resized
                current_size = (console.size.width, console.size.height)
                terminal_resized = last_terminal_size != current_size
                if terminal_resized:
                    last_terminal_size = current_size

                # Check if track changed
                track_changed = (
                    dashboard_state["last_track"] != current_player_state.current_track
                )
                if track_changed:
                    if (
                        dashboard_state["last_track"]
                        and current_player_state.current_track
                    ):
                        # Get proper track info for previous track display
                        prev_track_info = get_current_track_metadata()
                        if prev_track_info:
                            ui.store_previous_track(prev_track_info, "played")
                    dashboard_state["last_track"] = current_player_state.current_track

                # Determine if we should update
                force_update = dashboard_state["should_update"]
                time_based_update = (current_time - last_update_time) >= 1.0
                should_update = (
                    force_update
                    or track_changed
                    or terminal_resized
                    or time_based_update
                )

                if should_update:
                    # Get metadata and database info
                    track_metadata = get_current_track_metadata()
                    db_info = get_current_track_db_info()

                    # Update the live dashboard
                    try:
                        dashboard = ui.render_dashboard(
                            current_player_state,
                            track_metadata,
                            db_info,
                            console.size.width,
                        )

                        # Only update in interactive terminals with proper support
                        if console.is_terminal and not console.is_dumb_terminal:
                            try:
                                # Hide cursor to prevent blinking
                                console.file.write("\033[?25l")
                                console.file.flush()

                                # Save cursor position
                                console.file.write("\033[s")
                                console.file.flush()

                                # Move to top and clear the entire dashboard area
                                console.file.write("\033[H")

                                # Clear dashboard area completely (20 lines to be safe)
                                for i in range(20):
                                    console.file.write("\033[2K")  # Clear entire line
                                    if i < 19:
                                        console.file.write("\033[B")  # Move down

                                # Return to top and render new dashboard
                                console.file.write("\033[H")
                                console.file.flush()

                                # Render dashboard in one operation
                                console.print(dashboard, end="")

                                # Add full-width colorful separator
                                from rich.text import Text

                                separator_text = Text()
                                for i in range(console.size.width):
                                    if i % 3 == 0:
                                        separator_text.append("─", style="cyan")
                                    elif i % 3 == 1:
                                        separator_text.append("─", style="blue")
                                    else:
                                        separator_text.append("─", style="magenta")
                                console.print(separator_text)

                                # Restore cursor position
                                console.file.write("\033[u")

                                # Show cursor again
                                console.file.write("\033[?25h")
                                console.file.flush()

                            except Exception:
                                # If cursor positioning fails, skip real-time updates
                                pass
                    except Exception:
                        # Fallback if dashboard rendering fails
                        pass

                    dashboard_state["should_update"] = False
                    last_update_time = current_time

                # Update more frequently during playback
                update_interval = (
                    1.0
                    if (
                        current_player_state.is_playing
                        and current_player_state.current_track
                    )
                    else 3.0
                )
                time.sleep(update_interval)

            except Exception:
                # Silently handle errors to prevent crash
                time.sleep(1.0)

    # Reserve space for dashboard at top
    console.clear()
    dashboard = ui.render_dashboard(None, None, None, console.size.width)
    console.print(dashboard)
    console.print("─" * console.size.width)
    console.print()

    # Show welcome message in command area
    console.print("[bold green]Welcome to Music Minion CLI![/bold green]")
    console.print(
        "Type 'help' for available commands, '/' for command palette, or 'quit' to exit."
    )
    console.print(
        "💡 [dim]Tip: Use Tab for autocomplete, type to search playlists and commands[/dim]"
    )
    console.print()

    # Start background dashboard updater
    updater_thread = threading.Thread(target=dashboard_updater, daemon=True)
    updater_thread.start()

    # Create prompt_toolkit session with styling
    try:
        while True:
            try:
                # Pause background dashboard updates while getting input
                original_running_state = dashboard_state["running"]
                dashboard_state["running"] = False
                time.sleep(0.05)  # Give background thread time to stop

                try:
                    # Use command palette as the default input method
                    user_input = command_palette.show_command_palette()

                    if not user_input:
                        # Cancelled - resume and continue
                        continue
                finally:
                    # Resume background dashboard updates
                    dashboard_state["running"] = original_running_state
                    dashboard_state["should_update"] = True  # Force redraw

                # Skip empty input
                if not user_input:
                    continue

                # Strip leading / if present
                if user_input.startswith("/"):
                    user_input = user_input[1:]

                command, args = parsers.parse_command(user_input)

                # Add UI feedback for certain commands
                if command == "love":
                    ui.flash_love()
                elif command == "like":
                    ui.flash_like()
                elif command == "skip":
                    ui.flash_skip()
                elif command == "archive":
                    ui.flash_archive()
                elif command == "note" and args:
                    ui.flash_note_added()

                # Execute command with context
                ctx = helpers.create_context_from_globals()
                ctx, should_continue = router.handle_command(ctx, command, args)
                helpers.sync_context_to_globals(ctx)

                if not should_continue:
                    break

                # For state-changing commands, update dashboard immediately
                state_changing_commands = [
                    "play",
                    "pause",
                    "resume",
                    "stop",
                    "skip",
                    "archive",
                    "like",
                    "love",
                    "note",
                ]
                if command in state_changing_commands:
                    # Trigger immediate dashboard update
                    dashboard_state["should_update"] = True

                    # Manual dashboard refresh for state changes
                    try:
                        # Update player state first
                        if current_player_state.process:
                            current_player_state = playback.update_player_status(
                                current_player_state
                            )

                        track_metadata = get_current_track_metadata()
                        db_info = get_current_track_db_info()
                        dashboard = ui.render_dashboard(
                            current_player_state,
                            track_metadata,
                            db_info,
                            console.size.width,
                        )

                        # Show updated dashboard after state change
                        console.print("\n" + "─" * console.size.width)
                        console.print("📍 Current Status:")
                        console.print(dashboard)
                        console.print("─" * console.size.width)

                        # Also trigger the background updater to update the top dashboard
                        dashboard_state["should_update"] = True
                        dashboard_state["last_track"] = (
                            current_player_state.current_track
                        )

                    except Exception as e:
                        # Silently handle errors
                        pass

            except KeyboardInterrupt:
                console.print(
                    "\n[yellow]Use 'quit' or 'exit' to leave gracefully.[/yellow]"
                )
            except EOFError:
                console.print("\n[green]Goodbye![/green]")
                break

    except Exception as e:
        console.print(f"[red]Dashboard error: {e}[/red]")
    finally:
        # Stop background updater
        dashboard_state["running"] = False


def interactive_mode_blessed(web_processes: tuple | None = None) -> None:
    """Run the interactive mode with blessed UI."""
    global current_config, current_player_state, music_tracks

    # Always load config from file
    current_config = config.load_config()

    # Note: Logging is already initialized in interactive_mode()
    # No need to reinitialize here - that would clear all handlers!

    # Load music library using context
    ctx = helpers.create_context_from_globals()
    ctx, success = helpers.ensure_library_loaded(ctx)
    helpers.sync_context_to_globals(ctx)
    if not success:
        return

    # Auto-sync on startup if enabled (run in background thread)
    if current_config.sync.auto_sync_on_startup:
        sync_thread = threading.Thread(
            target=_auto_sync_background,
            args=(current_config,),
            daemon=True,
            name="AutoSyncThread",
        )
        sync_thread.start()

    # Run blessed UI with AppContext
    try:
        from .ui.blessed import run_interactive_ui

        ctx = run_interactive_ui(ctx)
        # Sync updated context back to globals
        helpers.sync_context_to_globals(ctx)
    finally:
        # Clean up MPV player (isolated error handling)
        try:
            if playback.is_mpv_running(ctx.player_state):
                playback.stop_mpv(ctx.player_state)
        except Exception:
            pass  # Ensure MPV errors don't prevent web process cleanup

        # Stop web processes if running (isolated error handling)
        cleanup_web_processes_safe(web_processes)


def interactive_mode() -> None:
    """Run the interactive command loop.

    TODO: Refactor interactive_mode() into smaller functions
    Suggested: setup_web_mode(), setup_dev_mode(), run_blessed_ui_mode(), run_simple_mode()
    See: CLAUDE.md guideline (functions ≤20 lines)
    """
    global current_config, current_player_state, music_tracks
    global file_watcher_observer, file_watcher_handler
    import os
    from .context import AppContext

    # Initialize variables for cleanup
    web_processes = None
    file_watcher_observer = None

    try:
        # Always load config from file
        current_config = config.load_config()

        # Initialize logging from config
        from music_minion.core.config import get_data_dir

        log_file = (
            Path(current_config.logging.log_file)
            if current_config.logging.log_file
            else (get_data_dir() / "music-minion.log")
        )
        setup_loguru(log_file, level=current_config.logging.level)

        # Run database migrations on startup
        database.init_database()

        # Check if web mode enabled
        web_mode = os.environ.get("MUSIC_MINION_WEB_MODE") == "1"

        if web_mode:
            from . import web_launcher

            # Pre-flight checks with config
            success, error = web_launcher.check_web_prerequisites(current_config.web)
            if not success:
                safe_print(f"❌ Cannot start web mode: {error}", style="red")
                return

            # Start web processes with config
            safe_print("🌐 Starting web services...", style="cyan")
            uvicorn_proc, vite_proc = web_launcher.start_web_processes(
                current_config.web
            )
            web_processes = (uvicorn_proc, vite_proc)

            # Print access URLs with actual config values
            safe_print(
                f"   Backend:  http://{current_config.web.backend_host}:{current_config.web.backend_port}",
                style="green",
            )
            safe_print(
                f"   Frontend: http://localhost:{current_config.web.frontend_port}",
                style="green",
            )
            safe_print("   Logs: /tmp/music-minion-{uvicorn,vite}.log", style="dim")

        # Setup hot-reload if --dev flag was passed
        dev_mode = os.environ.get("MUSIC_MINION_DEV_MODE") == "1"

        if dev_mode:
            try:
                from . import dev_reload

                def on_file_change(filepath: str) -> None:
                    """Callback for file changes - reload the module."""
                    success = dev_reload.reload_module(filepath)
                    if success:
                        filename = Path(filepath).name
                        safe_print(f"🔄 Reloaded: {filename}", style="cyan")

                observer_result = dev_reload.setup_file_watcher(on_file_change)

                if observer_result:
                    file_watcher_observer, file_watcher_handler = observer_result
                    safe_print("🔥 Hot-reload enabled", style="green bold")
                else:
                    safe_print("⚠️  Hot-reload setup failed", style="yellow")
            except ImportError:
                safe_print(
                    "⚠️  watchdog not installed - hot-reload disabled", style="yellow"
                )
                safe_print("   Install with: uv pip install watchdog", style="dim")

        # Auto-sync is now handled by blessed UI after first render (instant startup)
        # The blessed UI starts context-aware background sync after displaying the dashboard

        # Check if dashboard is enabled
        if current_config.ui.enable_dashboard:
            try:
                # Use blessed UI (new implementation)
                interactive_mode_blessed(web_processes)
            except ImportError:
                # blessed not available, fall back to old dashboard
                logger.exception(
                    "blessed UI not available, falling back to legacy dashboard"
                )
                safe_print(
                    "⚠️  blessed UI not available, falling back to legacy dashboard",
                    style="yellow",
                )
                try:
                    interactive_mode_with_dashboard()
                except Exception:
                    # Fall back to simple mode
                    pass
            except Exception:
                # Blessed UI failed for other reasons, fall back to simple mode
                logger.exception("Blessed UI failed, falling back to simple mode")
                safe_print(
                    "⚠️  Blessed UI failed, falling back to simple mode",
                    style="yellow",
                )
            finally:
                # Stop web processes if running (isolated error handling)
                cleanup_web_processes_safe(web_processes)

                # Clean up file watcher if enabled (isolated error handling)
                cleanup_file_watcher_safe(file_watcher_observer)
            return

        # Fallback to simple mode with Rich Console for consistent styling
        from rich.console import Console

        console_instance = Console()

        # Create initial application context
        ctx = AppContext.create(current_config, console_instance)

        # Load music library into context
        ctx = ctx.with_tracks(music_tracks)

        console_instance.print("[bold green]Welcome to Music Minion CLI![/bold green]")
        console_instance.print("Type 'help' for available commands, or 'quit' to exit.")
        console_instance.print()

        try:
            should_continue = True
            while should_continue:
                # Check for track completion periodically (context-based)
                ctx = helpers.check_and_handle_track_completion(ctx)

                # Process pending file changes if in dev mode
                if file_watcher_handler:
                    try:
                        from . import dev_reload

                        ready_files = file_watcher_handler.check_pending_changes()
                        for filepath in ready_files:
                            success = dev_reload.reload_module(filepath)
                            if success:
                                filename = Path(filepath).name
                                console_instance.print(
                                    f"🔄 Reloaded: {filename}", style="cyan"
                                )
                    except Exception:
                        pass  # Silently ignore reload errors

                try:
                    user_input = input("music-minion> ").strip()
                    command, args = parsers.parse_command(user_input)

                    # Execute command with context
                    ctx, should_continue = router.handle_command(ctx, command, args)

                    # Sync global state from context for backward compatibility with dashboard modes
                    current_player_state = ctx.player_state
                    music_tracks = ctx.music_tracks
                    current_config = ctx.config

                except KeyboardInterrupt:
                    console_instance.print(
                        "\n[yellow]Use 'quit' or 'exit' to leave gracefully.[/yellow]"
                    )
                except EOFError:
                    console_instance.print("\n[green]Goodbye![/green]")
                    break

        except Exception as e:
            console_instance.print(f"[red]An unexpected error occurred: {e}[/red]")
            sys.exit(1)
        finally:
            # Clean up file watcher if enabled (isolated error handling)
            cleanup_file_watcher_safe(file_watcher_observer)

    except KeyboardInterrupt:
        # Handle CTRL-C gracefully
        safe_print("\n[yellow]Interrupted by user. Cleaning up...[/yellow]")
    finally:
        # Stop web processes if running (isolated error handling for guaranteed cleanup)
        cleanup_web_processes_safe(web_processes)

        # Clean up file watcher if enabled (isolated error handling)
        cleanup_file_watcher_safe(file_watcher_observer)
        return

    # Fallback to simple mode with Rich Console for consistent styling
    from rich.console import Console

    console_instance = Console()

    # Create initial application context
    ctx = AppContext.create(current_config, console_instance)

    # Load music library into context
    ctx = ctx.with_tracks(music_tracks)

    console_instance.print("[bold green]Welcome to Music Minion CLI![/bold green]")
    console_instance.print("Type 'help' for available commands, or 'quit' to exit.")
    console_instance.print()

    try:
        should_continue = True
        while should_continue:
            # Check for track completion periodically (context-based)
            ctx = helpers.check_and_handle_track_completion(ctx)

            # Process pending file changes if in dev mode
            if file_watcher_handler:
                try:
                    from . import dev_reload

                    ready_files = file_watcher_handler.check_pending_changes()
                    for filepath in ready_files:
                        success = dev_reload.reload_module(filepath)
                        if success:
                            filename = Path(filepath).name
                            console_instance.print(
                                f"🔄 Reloaded: {filename}", style="cyan"
                            )
                except Exception:
                    pass  # Silently ignore reload errors

            try:
                user_input = input("music-minion> ").strip()
                command, args = parsers.parse_command(user_input)

                # Execute command with context
                ctx, should_continue = router.handle_command(ctx, command, args)

                # Sync global state from context for backward compatibility with dashboard modes
                current_player_state = ctx.player_state
                music_tracks = ctx.music_tracks
                current_config = ctx.config

            except KeyboardInterrupt:
                console_instance.print(
                    "\n[yellow]Use 'quit' or 'exit' to leave gracefully.[/yellow]"
                )
            except EOFError:
                console_instance.print("\n[green]Goodbye![/green]")
                break

    except Exception as e:
        console_instance.print(f"[red]An unexpected error occurred: {e}[/red]")
        sys.exit(1)
    finally:
        # Stop web processes if running (isolated error handling for guaranteed cleanup)
        cleanup_web_processes_safe(web_processes)

        # Clean up file watcher if enabled (isolated error handling)
        cleanup_file_watcher_safe(file_watcher_observer)
