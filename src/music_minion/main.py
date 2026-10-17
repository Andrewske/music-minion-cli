"""
Music Minion CLI - Main entry point and interactive loop
"""

import atexit
import os
import signal
import sys
import threading
from pathlib import Path
from typing import Any, List

from loguru import logger
from rich.console import Console

from music_minion.core import config
from music_minion.core import database
from music_minion.core.output import setup_loguru
from music_minion.context import AppContext
from music_minion.domain import library
from music_minion.domain import playback
from music_minion.domain import sync
from music_minion import router
from music_minion import web_launcher
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
console = Console()


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
    except Exception:
        logger.exception("Background sync failed")


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


def setup_web_mode(current_config: config.Config) -> tuple[Any, Any] | None:
    """Setup web mode processes if enabled."""
    # Check if web mode enabled
    web_mode = os.environ.get("MUSIC_MINION_WEB_MODE") == "1"

    if not web_mode:
        return None

    # Pre-flight checks with config
    success, error = web_launcher.check_web_prerequisites(current_config.web)
    if not success:
        safe_print(f"❌ Cannot start web mode: {error}", style="red")
        return None

    # Start web processes with config
    safe_print("🌐 Starting web services...", style="cyan")

    uvicorn_proc, vite_proc = web_launcher.start_web_processes(current_config.web)
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
    safe_print("   Logs: music-minion-{uvicorn,vite}.log", style="dim")

    return web_processes


def setup_dev_mode() -> tuple[Any, Any] | None:
    """Setup hot-reload file watcher if dev mode enabled."""
    # Setup hot-reload if --dev flag was passed
    dev_mode = os.environ.get("MUSIC_MINION_DEV_MODE") == "1"

    if not dev_mode:
        return None

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
            return (file_watcher_observer, file_watcher_handler)
        else:
            safe_print("⚠️  Hot-reload setup failed", style="yellow")
            return None
    except ImportError:
        safe_print("⚠️  watchdog not installed - hot-reload disabled", style="yellow")
        safe_print("   Install with: uv pip install watchdog", style="dim")
        return None


def run_blessed_ui_mode(web_processes: tuple | None) -> None:
    """Run blessed UI mode with fallbacks."""
    try:
        # Use blessed UI (new implementation)
        interactive_mode_blessed(web_processes)
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


def run_simple_mode(
    current_config: config.Config,
    music_tracks: List[library.Track],
    file_watcher_handler: Any | None,
    file_watcher_observer: Any | None,
) -> None:
    """Run simple mode with Rich console interactive loop."""
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
                    logger.debug("Hot-reload error ignored", exc_info=True)
                    pass  # Silently ignore reload errors

            try:
                user_input = input("music-minion> ").strip()
                command, args = parsers.parse_command(user_input)

                # Execute command with context
                ctx, should_continue = router.handle_command(ctx, command, args)

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


def interactive_mode() -> None:
    """Run the interactive command loop."""
    global current_config, current_player_state, music_tracks
    global file_watcher_observer, file_watcher_handler

    # Initialize variables for cleanup
    web_processes = None
    file_watcher_observer = None
    file_watcher_handler = None

    try:
        # Always load config from file
        current_config = config.load_config()

        # Initialize logging from config
        from music_minion.core.config import get_data_dir, get_project_root

        project_root = get_project_root()
        log_file = (
            Path(current_config.logging.log_file)
            if current_config.logging.log_file
            else (
                project_root / "music-minion.log"
                if project_root
                else get_data_dir() / "music-minion.log"
            )
        )
        setup_loguru(log_file, level=current_config.logging.level)

        # Run database migrations on startup
        database.init_database()

        # Setup web mode
        web_processes = setup_web_mode(current_config)

        # Setup dev mode
        dev_result = setup_dev_mode()
        if dev_result:
            file_watcher_observer, file_watcher_handler = dev_result

        # Register cleanup handlers as backup (in case finally block doesn't run)
        def emergency_cleanup() -> None:
            cleanup_web_processes_safe(web_processes)
            cleanup_file_watcher_safe(file_watcher_observer)

        atexit.register(emergency_cleanup)

        def signal_handler(sig: int, frame: Any) -> None:
            logger.info(f"Received signal {sig}, cleaning up...")
            emergency_cleanup()
            sys.exit(0)

        signal.signal(signal.SIGTERM, signal_handler)
        # Note: SIGINT is handled by KeyboardInterrupt, but add as backup
        signal.signal(signal.SIGINT, signal_handler)

        # Check if dashboard is enabled
        if current_config.ui.enable_dashboard:
            run_blessed_ui_mode(web_processes)
            return

        # Fallback to simple mode
        run_simple_mode(
            current_config, music_tracks, file_watcher_handler, file_watcher_observer
        )

    except KeyboardInterrupt:
        # Handle CTRL-C gracefully
        safe_print("\n[yellow]Interrupted by user. Cleaning up...[/yellow]")
    finally:
        # Stop web processes if running (isolated error handling for guaranteed cleanup)
        cleanup_web_processes_safe(web_processes)

        # Clean up file watcher if enabled (isolated error handling)
        cleanup_file_watcher_safe(file_watcher_observer)
