"""
Music Minion CLI - Main entry point and interactive loop
"""

import sys
import threading
import time
from pathlib import Path
from typing import List, Optional

from .core import config
from .core import database
from .domain import library
from . import player
from . import ai
from . import ui
from . import playlist
from . import playback
from . import sync
from . import command_palette
from . import router
from . import core

# Global state for interactive mode
current_player_state: player.PlayerState = player.PlayerState()
music_tracks: List[library.Track] = []
current_config: config.Config = config.Config()

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


def play_track(track: library.Track, playlist_position: Optional[int] = None) -> bool:
    """
    Play a specific track.

    Args:
        track: Track to play
        playlist_position: Optional 0-based position in active playlist (optimization to avoid lookup)

    Returns:
        True to continue interactive loop
    """
    global current_player_state, current_config

    # Start MPV if not running
    if not player.is_mpv_running(current_player_state):
        print("Starting music player...")
        new_state = player.start_mpv(current_config)
        if not new_state:
            print("Failed to start music player")
            return True
        current_player_state = new_state

    # Play the track
    new_state, success = player.play_file(current_player_state, track.file_path)
    current_player_state = new_state

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


def check_and_handle_track_completion() -> None:
    """Check if current track has completed and handle auto-analysis."""
    global current_player_state, music_tracks

    if not current_player_state.current_track:
        return  # No message needed - track already handled

    if not player.is_mpv_running(current_player_state):
        return  # Player not running, nothing to check

    # Check if track is still playing
    status = player.get_player_status(current_player_state)
    position, duration, percent = player.get_progress_info(current_player_state)

    # If track has ended (reached 100% or very close), trigger analysis and play next
    if duration > 0 and percent >= 99.0 and not status.get('playing', False):
        # Find the track that just finished
        finished_track = None
        for track in music_tracks:
            if track.file_path == current_player_state.current_track:
                finished_track = track
                break

        if finished_track:
            safe_print(f"✅ Finished: {library.get_display_name(finished_track)}", "green")

            # Check if track is archived (don't analyze archived tracks)
            track_id = get_current_track_id()
            if track_id:
                # Check if track is archived
                archived_tracks = database.get_archived_tracks()
                if track_id not in archived_tracks:
                    # Trigger auto-analysis in background
                    try:
                        safe_print(f"🤖 Auto-analyzing completed track...", "cyan")
                        result = ai.analyze_and_tag_track(finished_track, 'auto_analysis')

                        if result['success'] and result['tags_added']:
                            safe_print(f"✅ Added {len(result['tags_added'])} AI tags: {', '.join(result['tags_added'])}", "green")
                        elif not result['success']:
                            error_msg = result.get('error', 'Unknown error')
                            # Show brief error message but don't be too intrusive
                            if 'API key' in error_msg:
                                safe_print("⚠️  AI analysis skipped: No API key configured (use 'ai setup <key>')", "yellow")
                            else:
                                safe_print(f"⚠️  AI analysis failed: {error_msg}", "yellow")
                    except Exception as e:
                        # Don't interrupt user experience with detailed errors
                        safe_print(f"⚠️  AI analysis error: {str(e)}", "yellow")

        # Clear current track and play next track automatically
        current_player_state = current_player_state._replace(current_track=None)

        # Auto-play next track if continuous playback is enabled
        safe_print("⏭️  Auto-playing next track...", "blue")

        # Get available tracks (excluding archived ones)
        available_tracks = get_available_tracks()

        # Remove the track that just finished from options if possible
        if finished_track and len(available_tracks) > 1:
            available_tracks = [t for t in available_tracks if t.file_path != finished_track.file_path]

        if available_tracks:
            next_track = library.get_random_track(available_tracks)
            if next_track:
                play_track(next_track)
        else:
            safe_print("No more tracks to play (all may be archived)", "red")


def get_available_tracks() -> List[library.Track]:
    """
    Get tracks that are available for playback.
    Respects active playlist if one is set, and excludes archived tracks.
    """
    global music_tracks

    if not music_tracks:
        return []

    # Check if there's an active playlist
    active = playlist.get_active_playlist()

    if active:
        # Get tracks from active playlist (already excludes archived)
        playlist_file_paths = set(playlist.get_available_playlist_tracks(active['id']))

        if not playlist_file_paths:
            return []

        # Convert file paths to Track objects
        available_tracks = []
        for track in music_tracks:
            if track.file_path in playlist_file_paths and Path(track.file_path).exists():
                available_tracks.append(track)

        return available_tracks
    else:
        # No active playlist - use normal behavior (all non-archived tracks)
        # Try to get available tracks directly from database (faster)
        try:
            db_tracks = database.get_available_tracks()
            if db_tracks:
                # Convert database tracks to library Track objects and filter existing files
                available_tracks = []
                for db_track in db_tracks:
                    track = database.db_track_to_library_track(db_track)
                    if Path(track.file_path).exists():
                        available_tracks.append(track)
                return available_tracks
        except Exception:
            # Fall back to in-memory filtering if database query fails
            pass

        # Fallback: filter in-memory tracks
        archived_track_ids = set(database.get_archived_tracks())

        if not archived_track_ids:
            return music_tracks

        # Filter out archived tracks
        available_tracks = []
        for track in music_tracks:
            # Check if track is archived by getting its database ID
            track_id = database.get_track_by_path(track.file_path)
            if not track_id or track_id['id'] not in archived_track_ids:
                available_tracks.append(track)

        return available_tracks


def get_current_track_id() -> Optional[int]:
    """Get the database ID of the currently playing track."""
    global current_player_state, music_tracks

    if not current_player_state.current_track:
        return None

    # Find the track in our library
    for track in music_tracks:
        if track.file_path == current_player_state.current_track:
            # Get or create track ID in database
            return database.get_or_create_track(
                track.file_path, track.title, track.artist, track.album,
                track.genre, track.year, track.duration, track.key, track.bpm
            )

    return None


def _auto_sync_background(cfg: config.Config) -> None:
    """Background thread function for auto-sync on startup.

    Runs sync_import silently in the background without blocking UI startup.
    Any errors are caught and logged without interrupting the main thread.
    """
    try:
        sync.sync_import(cfg, force_all=False, show_progress=False)
    except Exception as e:
        print(f"⚠️  Background sync failed: {e}")


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
            name="AutoSyncThread"
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
            if str(t.file_path) == current_player_state.current_track:
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
                if str(t.file_path) == current_player_state.current_track:
                    track = t
                    break

            if not track:
                return None

            # Get track ID from database
            track_id = database.get_or_create_track(
                track.file_path, track.title, track.artist, track.album,
                track.genre, track.year, track.duration, track.key, track.bpm
            )

            # Get tags
            tags_data = database.get_track_tags(track_id)
            tags = [t['tag_name'] for t in tags_data if not t.get('blacklisted', False)]

            # Get latest rating
            ratings = database.get_track_ratings(track_id)
            latest_rating = None
            if ratings:
                # Convert rating type to numeric score
                rating_map = {"archive": 0, "skip": 25, "like": 60, "love": 85}
                latest_rating = rating_map.get(ratings[0]['rating_type'], 50)

            # Get notes
            notes_data = database.get_track_notes(track_id)
            latest_note = notes_data[0]['note'] if notes_data else ""

            # Get play stats
            play_count = len(ratings)
            last_played = ratings[0]['created_at'] if ratings else None

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
        global current_player_state
        last_update_time = time.time()
        last_terminal_size = None

        while dashboard_state["running"]:
            try:
                current_time = time.time()

                # Check for track completion
                check_and_handle_track_completion()

                # Update player state
                if current_player_state.process:
                    current_player_state = player.update_player_status(current_player_state)

                # Check if terminal was resized
                current_size = (console.size.width, console.size.height)
                terminal_resized = last_terminal_size != current_size
                if terminal_resized:
                    last_terminal_size = current_size

                # Check if track changed
                track_changed = dashboard_state["last_track"] != current_player_state.current_track
                if track_changed:
                    if dashboard_state["last_track"] and current_player_state.current_track:
                        # Get proper track info for previous track display
                        prev_track_info = get_current_track_metadata()
                        if prev_track_info:
                            ui.store_previous_track(prev_track_info, "played")
                    dashboard_state["last_track"] = current_player_state.current_track

                # Determine if we should update
                force_update = dashboard_state["should_update"]
                time_based_update = (current_time - last_update_time) >= 1.0
                should_update = force_update or track_changed or terminal_resized or time_based_update

                if should_update:
                    # Get metadata and database info
                    track_metadata = get_current_track_metadata()
                    db_info = get_current_track_db_info()

                    # Update the live dashboard
                    try:
                        dashboard = ui.render_dashboard(current_player_state, track_metadata, db_info, console.size.width)

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
                update_interval = 1.0 if (current_player_state.is_playing and current_player_state.current_track) else 3.0
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
    console.print("Type 'help' for available commands, '/' for command palette, or 'quit' to exit.")
    console.print("💡 [dim]Tip: Use Tab for autocomplete, type to search playlists and commands[/dim]")
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
                if user_input.startswith('/'):
                    user_input = user_input[1:]

                command, args = core.parse_command(user_input)

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

                if not router.handle_command(command, args):
                    break

                # For state-changing commands, update dashboard immediately
                state_changing_commands = ["play", "pause", "resume", "stop", "skip", "archive", "like", "love", "note"]
                if command in state_changing_commands:
                    # Trigger immediate dashboard update
                    dashboard_state["should_update"] = True
                    # Give a moment for the command to take effect
                    time.sleep(0.1)

                    # Manual dashboard refresh for state changes
                    try:
                        # Update player state first
                        if current_player_state.process:
                            current_player_state = player.update_player_status(current_player_state)

                        track_metadata = get_current_track_metadata()
                        db_info = get_current_track_db_info()
                        dashboard = ui.render_dashboard(current_player_state, track_metadata, db_info, console.size.width)

                        # Show updated dashboard after state change
                        console.print("\n" + "─" * console.size.width)
                        console.print("📍 Current Status:")
                        console.print(dashboard)
                        console.print("─" * console.size.width)

                        # Also trigger the background updater to update the top dashboard
                        dashboard_state["should_update"] = True
                        dashboard_state["last_track"] = current_player_state.current_track

                    except Exception as e:
                        # Silently handle errors
                        pass

            except KeyboardInterrupt:
                console.print("\n[yellow]Use 'quit' or 'exit' to leave gracefully.[/yellow]")
            except EOFError:
                console.print("\n[green]Goodbye![/green]")
                break

    except Exception as e:
        console.print(f"[red]Dashboard error: {e}[/red]")
    finally:
        # Stop background updater
        dashboard_state["running"] = False


def interactive_mode_textual() -> None:
    """Run the interactive mode with Textual UI."""
    global current_config, current_player_state, music_tracks

    # Load config if not already loaded
    if not current_config.music.library_paths:
        current_config = config.load_config()

    # Load music library
    core.ensure_library_loaded()

    # Run database migrations on startup
    database.init_database()

    # Auto-sync on startup if enabled (run in background thread)
    if current_config.sync.auto_sync_on_startup:
        sync_thread = threading.Thread(
            target=_auto_sync_background,
            args=(current_config,),
            daemon=True,
            name="AutoSyncThread"
        )
        sync_thread.start()

    # Create the runner with current state
    from .ui_textual import MusicMinionRunner
    runner = MusicMinionRunner(current_config, music_tracks, current_player_state)

    # Create command handler wrapper that works with Textual app
    def textual_command_handler(command: str, args: List[str]) -> bool:
        """Wrapper for handle_command that integrates with Textual app"""
        # Get reference to the Textual app for printing
        app = runner.app

        # Special handling for "playlist" command - show Textual modal
        if command == "playlist" and not args:
            # Show playlist browser modal
            try:
                from . import playlist as playlist_module

                playlists = playlist_module.get_playlists_sorted_by_recent()

                if not playlists:
                    app.print_error("No playlists found. Create one with: playlist new manual <name>")
                    return True

                # Get active playlist
                active = playlist_module.get_active_playlist()
                active_id = active['id'] if active else None

                # Define handler for playlist selection
                def handle_playlist_selection(selected: dict | None) -> None:
                    """Handle playlist selection from modal"""
                    if selected:
                        # Activate playlist
                        if playlist_module.set_active_playlist(selected['id']):
                            app.print_success(f"Activated playlist: {selected['name']}")

                            # Auto-play first track
                            playlist_tracks = playlist_module.get_playlist_tracks(selected['id'])
                            if playlist_tracks:
                                # Convert DB track to library.Track and play
                                first_track = database.db_track_to_library_track(playlist_tracks[0])
                                if play_track(first_track, playlist_position=0):
                                    app.print_info(f"🎵 Now playing: {library.get_display_name(first_track)}")
                                else:
                                    app.print_error("Failed to play track")
                            else:
                                app.print_info(f"⚠️  Playlist is empty")
                        else:
                            app.print_error(f"Failed to activate playlist")

                # Show modal
                from .ui_textual.playlist_modal import PlaylistModal
                app.push_screen(
                    PlaylistModal(playlists, active_id),
                    handle_playlist_selection
                )

                return True

            except Exception as e:
                app.print_error(f"Error browsing playlists: {e}")
                import traceback
                traceback.print_exc()
                return True

        # Add UI feedback for rating commands
        if command == "love":
            runner.app_state.set_feedback("Track loved!", "❤️")
        elif command == "like":
            runner.app_state.set_feedback("Track liked!", "👍")
        elif command == "skip":
            runner.app_state.set_feedback("Skipped to next track", "⏭")
        elif command == "archive":
            runner.app_state.set_feedback("Track archived - won't play again", "🗄")
        elif command == "note" and args:
            runner.app_state.set_feedback("Note added to track", "📝")

        # Call the original command handler
        # Note: We need to redirect print statements to the Textual app
        import io
        import sys

        # Capture stdout
        old_stdout = sys.stdout
        stdout_capture = io.StringIO()
        sys.stdout = stdout_capture

        try:
            result = router.handle_command(command, args)

            # Get captured output and send to Textual app
            output = stdout_capture.getvalue()
            if output:
                for line in output.rstrip('\n').split('\n'):
                    if line.strip():
                        # Color code based on content
                        if line.startswith('❌') or 'Error' in line or 'Failed' in line:
                            app.print_error(line)
                        elif line.startswith('✅') or 'Success' in line:
                            app.print_success(line)
                        elif line.startswith('💡') or 'Tip:' in line:
                            app.print_info(line)
                        else:
                            app.print_output(line)

            return result

        finally:
            # Restore stdout
            sys.stdout = old_stdout

    # Set the command handler
    runner.set_command_handler(textual_command_handler)

    # Run the Textual app
    try:
        runner.run()
    finally:
        # Clean up MPV player
        if player.is_mpv_running(current_player_state):
            player.stop_mpv(current_player_state)


def interactive_mode_blessed() -> None:
    """Run the interactive mode with blessed UI."""
    global current_config, current_player_state, music_tracks

    # Load config if not already loaded
    if not current_config.music.library_paths:
        current_config = config.load_config()

    # Load music library
    core.ensure_library_loaded()

    # Run database migrations on startup
    database.init_database()

    # Auto-sync on startup if enabled (run in background thread)
    if current_config.sync.auto_sync_on_startup:
        sync_thread = threading.Thread(
            target=_auto_sync_background,
            args=(current_config,),
            daemon=True,
            name="AutoSyncThread"
        )
        sync_thread.start()

    # Create initial UI state
    from .ui_blessed.state import create_initial_state
    from dataclasses import replace

    initial_state = create_initial_state()
    # Populate state with config and library
    initial_state = replace(
        initial_state,
        config=current_config,
        music_tracks=music_tracks,
        shuffle_enabled=True,  # Default shuffle on
    )

    # Run blessed UI
    try:
        from .ui_blessed import run_interactive_ui
        run_interactive_ui(initial_state, current_player_state)
    finally:
        # Clean up MPV player
        if player.is_mpv_running(current_player_state):
            player.stop_mpv(current_player_state)


def interactive_mode() -> None:
    """Run the interactive command loop."""
    global current_config
    import os

    # Load config if not already loaded
    if not current_config.music.library_paths:
        current_config = config.load_config()

    # Run database migrations on startup
    database.init_database()

    # Auto-sync on startup if enabled (run in background thread)
    if current_config.sync.auto_sync_on_startup:
        print("🔄 Starting background sync...")
        sync_thread = threading.Thread(
            target=_auto_sync_background,
            args=(current_config,),
            daemon=True,
            name="AutoSyncThread"
        )
        sync_thread.start()

    # Check for UI mode preference (environment variable or default)
    ui_mode = os.environ.get('MUSIC_MINION_UI', 'blessed').lower()

    # Check if dashboard is enabled
    if current_config.ui.enable_dashboard:
        try:
            # Use blessed UI by default (new implementation)
            if ui_mode == 'blessed':
                interactive_mode_blessed()
                return
            elif ui_mode == 'textual':
                # Use Textual UI if specifically requested
                interactive_mode_textual()
                return
        except ImportError as e:
            # blessed/Textual not available, fall back to old dashboard
            print(f"⚠️  {ui_mode.title()} UI not available ({e}), falling back to legacy dashboard")
            try:
                interactive_mode_with_dashboard()
                return
            except Exception:
                # Fall back to simple mode
                pass

    # Fallback to simple mode with Rich Console for consistent styling
    from rich.console import Console
    console = Console()

    console.print("[bold green]Welcome to Music Minion CLI![/bold green]")
    console.print("Type 'help' for available commands, or 'quit' to exit.")
    console.print()

    try:
        while True:
            # Check for track completion periodically
            check_and_handle_track_completion()

            try:
                user_input = input("music-minion> ").strip()
                command, args = core.parse_command(user_input)

                if not router.handle_command(command, args):
                    break

            except KeyboardInterrupt:
                console.print("\n[yellow]Use 'quit' or 'exit' to leave gracefully.[/yellow]")
            except EOFError:
                console.print("\n[green]Goodbye![/green]")
                break

    except Exception as e:
        console.print(f"[red]An unexpected error occurred: {e}[/red]")
        import sys
        sys.exit(1)


def main() -> None:
    """Main entry point for the music-minion command."""

    # Only run interactive mode for now until we have a way to manage state across sessions
    interactive_mode()
    # if len(sys.argv) == 1:
    #     # No arguments provided, start interactive mode
    #     interactive_mode()
    # else:
    #     # Command line arguments provided, execute single command
    #     command_parts = sys.argv[1:]
    #     command = command_parts[0].lower() if command_parts else ""
    #     args = command_parts[1:] if len(command_parts) > 1 else []

    #     handle_command(command, args)


if __name__ == "__main__":
    main()
