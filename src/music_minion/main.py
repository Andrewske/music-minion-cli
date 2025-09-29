"""
Music Minion CLI - Main entry point and interactive loop
"""

import sys
from pathlib import Path
from typing import List, Optional

from . import config
from . import database
from . import library
from . import player
from . import ai
from . import ui
from . import playlist
from . import playlist_filters

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


def parse_quoted_args(args: List[str]) -> List[str]:
    """
    Parse command arguments respecting quoted strings.
    Handles both single and double quotes.

    Args:
        args: Raw argument list from command split

    Returns:
        List of parsed arguments with quotes removed

    Example:
        ['playlist', 'rename', '"Old', 'Name"', '"New', 'Name"']
        -> ['playlist', 'rename', 'Old Name', 'New Name']
    """
    parsed = []
    current = []
    in_quote = False
    quote_char = None

    for arg in args:
        # Check if this arg starts a quote
        if not in_quote and arg and arg[0] in ('"', "'"):
            quote_char = arg[0]
            in_quote = True
            # Check if quote also ends in same arg
            if len(arg) > 1 and arg[-1] == quote_char:
                parsed.append(arg[1:-1])
                in_quote = False
                quote_char = None
            else:
                current.append(arg[1:])
        # Check if this arg ends the current quote
        elif in_quote and arg and arg[-1] == quote_char:
            current.append(arg[:-1])
            parsed.append(' '.join(current))
            current = []
            in_quote = False
            quote_char = None
        # Inside a quote
        elif in_quote:
            current.append(arg)
        # Regular arg outside quotes
        else:
            parsed.append(arg)

    # If we have unclosed quotes, join what we have
    if current:
        parsed.append(' '.join(current))

    return parsed


def print_help() -> None:
    """Display help information for available commands."""
    help_text = """
Music Minion CLI - Contextual Music Curation

Available commands:
  play [query]      Start playing music (random if no query, or search)
  pause             Pause current playback
  resume            Resume paused playback
  skip              Skip to next random song
  stop              Stop current playback
  killall           Kill all MPV processes (emergency stop)
  archive           Archive current song (never play again)
  like              Rate current song as liked
  love              Rate current song as loved
  note <text>       Add a note to the current song
  status            Show current song and player status
  stats             Show library and rating statistics
  scan              Scan library and populate database
  migrate           Run database migrations (if needed)

Playlist Commands:
  playlist                        List all playlists
  playlist new manual <name>      Create manual playlist
  playlist new smart <name>       Create smart playlist (filter wizard)
  playlist delete <name>          Delete playlist
  playlist rename "old" "new"     Rename playlist (use quotes)
  playlist show <name>            Show playlist tracks
  playlist active <name>          Set active playlist
  playlist active none            Clear active playlist
  add <playlist>                  Add current track to playlist
  remove <playlist>               Remove current track from playlist

AI Commands:
  ai setup <key>    Set up OpenAI API key for AI analysis
  ai analyze        Analyze current track with AI and add tags
  ai test           Test AI prompt with a random track and save report
  ai usage          Show total AI usage and costs
  ai usage today    Show today's AI usage
  ai usage month    Show last 30 days usage

Tag Commands:
  tag remove <tag>  Remove/blacklist a tag from current track
  tag list          Show all tags for current track

  init              Initialize configuration and scan library
  help              Show this help message
  quit, exit        Exit the program

Interactive mode:
  Just run 'music-minion' to enter interactive mode where you can
  type commands directly.

Examples:
  play                    # Play random song
  play daft punk          # Search and play Daft Punk track
  playlist new manual "NYE 2025"  # Create playlist
  add "NYE 2025"          # Add current track to playlist
"""
    print(help_text.strip())


def parse_command(user_input: str) -> tuple[str, List[str]]:
    """Parse user input into command and arguments."""
    parts = user_input.strip().split()
    if not parts:
        return "", []
    
    command = parts[0].lower()
    args = parts[1:] if len(parts) > 1 else []
    return command, args


def ensure_mpv_available() -> bool:
    """Check if MPV is available and warn if not."""
    if not player.check_mpv_available():
        print("Error: MPV is not installed or not available in PATH.")
        print("Please install MPV to use playback features.")
        print("On Ubuntu/Debian: sudo apt install mpv")
        print("On Arch Linux: sudo pacman -S mpv") 
        print("On macOS: brew install mpv")
        print("On Windows: Download from https://mpv.io/installation/ or use 'winget install mpv'")
        return False
    return True


def ensure_library_loaded() -> bool:
    """Ensure music library is loaded."""
    global music_tracks, current_config
    
    if not music_tracks:
        safe_print("Loading music library...", "blue")
        current_config = config.load_config()
        
        # Try to load from database first (much faster)
        db_tracks = database.get_all_tracks()
        if db_tracks:
            # Convert database tracks to library Track objects
            music_tracks = [database.db_track_to_library_track(track) for track in db_tracks]
            # Filter out files that no longer exist
            existing_tracks = []
            for track in music_tracks:
                if Path(track.file_path).exists():
                    existing_tracks.append(track)
            music_tracks = existing_tracks
            safe_print(f"Loaded {len(music_tracks)} tracks from database", "green")
        
        # If no database tracks or very few, fall back to filesystem scan
        if not music_tracks:
            safe_print("No tracks in database, scanning filesystem...", "yellow")
            music_tracks = library.scan_music_library(current_config, show_progress=False)
            
            if not music_tracks:
                safe_print("No music files found in configured library paths.", "red")
                safe_print("Run 'music-minion scan' to populate the database, or 'music-minion init' to set up library paths.", "yellow")
                return False
            
            safe_print(f"Scanned {len(music_tracks)} tracks from filesystem", "green")
    
    return True


def handle_play_command(args: List[str]) -> bool:
    """Handle play command - start playback or play specific track."""
    global current_player_state, current_config
    
    if not ensure_mpv_available() or not ensure_library_loaded():
        return True
    
    # If no arguments, play random track or resume current
    if not args:
        if current_player_state.current_track:
            # Resume current track
            new_state, success = player.resume_playback(current_player_state)
            current_player_state = new_state
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


def play_track(track: library.Track) -> bool:
    """Play a specific track."""
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


def handle_pause_command() -> bool:
    """Handle pause command."""
    global current_player_state
    
    if not player.is_mpv_running(current_player_state):
        print("No music is currently playing")
        return True
    
    new_state, success = player.pause_playback(current_player_state)
    current_player_state = new_state
    
    if success:
        print("⏸ Paused")
    else:
        print("Failed to pause playback")
    
    return True


def handle_resume_command() -> bool:
    """Handle resume command."""
    global current_player_state
    
    if not player.is_mpv_running(current_player_state):
        print("No music player is running")
        return True
    
    new_state, success = player.resume_playback(current_player_state)
    current_player_state = new_state
    
    if success:
        print("▶ Resumed")
    else:
        print("Failed to resume playback")
    
    return True


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


def handle_skip_command() -> bool:
    """Handle skip command - play next random track."""
    global current_player_state
    
    if not ensure_library_loaded():
        return True
    
    # Get available tracks (excluding archived ones)
    available_tracks = get_available_tracks()
    
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


def handle_stop_command() -> bool:
    """Handle stop command."""
    global current_player_state
    
    if not player.is_mpv_running(current_player_state):
        print("No music is currently playing")
        return True
    
    new_state, success = player.stop_playback(current_player_state)
    current_player_state = new_state
    
    if success:
        print("⏹ Stopped")
    else:
        print("Failed to stop playback")
    
    return True


def handle_status_command() -> bool:
    """Handle status command - show current player and track status."""
    global current_player_state, music_tracks
    
    print("Music Minion Status:")
    print("─" * 40)
    
    if not player.is_mpv_running(current_player_state):
        print("♪ Player: Not running")
        print("♫ Track: None")
        return True
    
    # Get current status from player
    status = player.get_player_status(current_player_state)
    position, duration, percent = player.get_progress_info(current_player_state)
    
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
                print(f"⏱  Progress: [{progress_bar}] {player.format_time(position)} / {player.format_time(duration)}")
            
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
    else:
        print("📋 Active Playlist: None (playing all tracks)")

    # Library stats
    if music_tracks:
        available = get_available_tracks()
        print(f"📚 Library: {len(music_tracks)} tracks loaded, {len(available)} available for playback")

    return True


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


def handle_archive_command() -> bool:
    """Handle archive command - mark current song to never play again."""
    global current_player_state, music_tracks
    
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
    global current_player_state, music_tracks
    
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
        from datetime import datetime
        now = datetime.now()
        time_context = f"{now.strftime('%A')} at {now.hour:02d}:{now.minute:02d}"
        print(f"   Liked on {time_context}")
    else:
        print("Failed to rate track")
    
    return True


def handle_love_command() -> bool:
    """Handle love command - rate current song as loved."""
    global current_player_state, music_tracks
    
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
        from datetime import datetime
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
    global current_player_state, music_tracks
    
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
        from datetime import datetime
        now = datetime.now()
        time_context = f"{now.strftime('%A')} at {now.hour:02d}:{now.minute:02d}"
        print(f"   Added on {time_context}")
        
        if note_id:
            print(f"   Note ID: {note_id} (for AI processing)")
    else:
        print("Failed to add note")
    
    return True


def handle_killall_command() -> bool:
    """Kill all MPV processes (emergency stop)."""
    import subprocess
    try:
        result = subprocess.run(['pkill', 'mpv'], capture_output=True)
        if result.returncode == 0:
            print("⛔ Killed all MPV processes")
        else:
            print("No MPV processes found")
        
        # Clean up any leftover sockets
        import os
        import glob
        sockets = glob.glob('/tmp/mpv-socket-*')
        for socket in sockets:
            try:
                os.unlink(socket)
            except OSError:
                pass
        if sockets:
            print(f"Cleaned up {len(sockets)} leftover socket(s)")
            
    except Exception as e:
        print(f"Error killing MPV: {e}")
    
    return True


def handle_stats_command() -> bool:
    """Handle stats command - show database statistics."""
    try:
        analytics = database.get_library_analytics()
        
        print("\n📊 Library Statistics")
        print("=" * 40)
        print(f"Total tracks: {analytics['total_tracks']}")
        print(f"Rated tracks: {analytics['rated_tracks']}")
        print(f"Total ratings: {analytics['total_ratings']}")
        
        if analytics['rating_distribution']:
            print("\n📈 Rating Distribution:")
            for rating_type, count in analytics['rating_distribution'].items():
                emoji = {'archive': '📦', 'skip': '⏭️', 'like': '👍', 'love': '❤️'}.get(rating_type, '❓')
                print(f"  {emoji} {rating_type}: {count}")
        
        if analytics['active_hours']:
            print("\n🕐 Most Active Hours:")
            for hour_data in analytics['active_hours'][:3]:
                hour = hour_data['hour']
                count = hour_data['count']
                print(f"  {hour:02d}:00 - {count} ratings")
        
        if analytics['active_days']:
            print("\n📅 Most Active Days:")
            for day_data in analytics['active_days'][:3]:
                print(f"  {day_data['day']}: {day_data['count']} ratings")
        
        # Show recent ratings
        recent = database.get_recent_ratings(5)
        if recent:
            print("\n🕒 Recent Ratings:")
            for rating in recent:
                rating_type = rating['rating_type']
                emoji = {'archive': '📦', 'skip': '⏭️', 'like': '👍', 'love': '❤️'}.get(rating_type, '❓')
                title = rating['title'] or 'Unknown'
                artist = rating['artist'] or 'Unknown'
                print(f"  {emoji} {artist} - {title}")
        
        return True
    except Exception as e:
        print(f"❌ Error getting stats: {e}")
        return False


def handle_scan_command() -> bool:
    """Handle scan command - scan library and populate database."""
    print("🔍 Starting library scan...")
    
    try:
        # Load config and scan library
        cfg = config.load_config()
        tracks = library.scan_music_library(cfg, show_progress=True)
        
        if not tracks:
            print("❌ No music files found in configured library paths")
            return True
        
        # Add all tracks to database
        print(f"\n💾 Adding {len(tracks)} tracks to database...")
        added = 0
        updated = 0
        errors = 0
        
        for track in tracks:
            try:
                # Check if track already exists
                existing = database.get_track_by_path(track.file_path)
                if existing:
                    updated += 1
                else:
                    added += 1
                
                # Add or update track in database
                database.get_or_create_track(
                    track.file_path, track.title, track.artist, track.album,
                    track.genre, track.year, track.duration, track.key, track.bpm
                )
            except Exception as e:
                errors += 1
                print(f"  Error processing {track.file_path}: {e}")
        
        # Show scan results
        print(f"\n✅ Scan complete!")
        print(f"  📝 New tracks: {added}")
        print(f"  🔄 Updated tracks: {updated}")
        if errors:
            print(f"  ⚠️  Errors: {errors}")
        
        # Show library stats
        stats = library.get_library_stats(tracks)
        print(f"\n📚 Library Overview:")
        print(f"  Total duration: {stats['total_duration_str']}")
        print(f"  Total size: {stats['total_size_str']}")
        print(f"  Artists: {stats['artists']}")
        print(f"  Albums: {stats['albums']}")
        
        if stats['formats']:
            print(f"\n📂 Formats:")
            for fmt, count in sorted(stats['formats'].items(), key=lambda x: x[1], reverse=True):
                print(f"  {fmt}: {count} files")
        
        if stats['avg_bpm']:
            print(f"\n🎵 DJ Metadata:")
            print(f"  Tracks with BPM: {stats['tracks_with_bpm']}")
            print(f"  Average BPM: {stats['avg_bpm']:.1f}")
            print(f"  Tracks with key: {stats['tracks_with_key']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error scanning library: {e}")
        import traceback
        traceback.print_exc()
        return False


def handle_ai_setup_command(args: List[str]) -> bool:
    """Handle ai setup command - configure OpenAI API key."""
    if not args:
        print("Error: Please provide an API key. Usage: ai setup <key>")
        return True
    
    api_key = args[0]
    
    try:
        ai.store_api_key(api_key)
        print("✅ OpenAI API key stored successfully")
        print("   Key stored in ~/.config/music-minion/.env")
        print("   You can also set OPENAI_API_KEY environment variable or create .env in project root")
        print("   You can now use AI analysis features")
    except Exception as e:
        print(f"❌ Error storing API key: {e}")
    
    return True


def handle_ai_analyze_command() -> bool:
    """Handle ai analyze command - analyze current track with AI."""
    global current_player_state, music_tracks
    
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
    
    print(f"🤖 Analyzing track: {library.get_display_name(current_track)}")
    
    try:
        result = ai.analyze_and_tag_track(current_track, 'manual_analysis')
        
        if result['success']:
            tags_added = result['tags_added']
            if tags_added:
                print(f"✅ Added {len(tags_added)} tags: {', '.join(tags_added)}")
            else:
                print("✅ Analysis complete - no new tags suggested")
            
            # Show token usage
            usage = result.get('token_usage', {})
            if usage:
                print(f"   Tokens used: {usage.get('prompt_tokens', 0)} prompt + {usage.get('completion_tokens', 0)} completion")
                print(f"   Response time: {usage.get('response_time_ms', 0)}ms")
        else:
            error_msg = result.get('error', 'Unknown error')
            print(f"❌ AI analysis failed: {error_msg}")
    
    except Exception as e:
        print(f"❌ Error during AI analysis: {e}")
    
    return True


def handle_ai_test_command() -> bool:
    """Handle ai test command - test AI prompt with random track."""
    try:
        print("🧪 Running AI prompt test with random track...")
        
        # Run the test
        test_results = ai.test_ai_prompt_with_random_track()
        
        if test_results['success']:
            # Save report
            report_file = ai.save_test_report(test_results)
            
            # Show summary
            track_info = test_results['track_info']
            print(f"✅ Test completed successfully!")
            print(f"   Track: {track_info.get('artist', 'Unknown')} - {track_info.get('title', 'Unknown')}")
            print(f"   Generated tags: {', '.join(test_results.get('ai_output_tags', []))}")
            
            token_usage = test_results.get('token_usage', {})
            print(f"   Tokens used: {token_usage.get('prompt_tokens', 0)} prompt + {token_usage.get('completion_tokens', 0)} completion")
            print(f"   Response time: {token_usage.get('response_time_ms', 0)}ms")
            
            print(f"📄 Full report saved: {report_file}")
            
        else:
            # Save report even for failed tests
            report_file = ai.save_test_report(test_results)
            error_msg = test_results.get('error', 'Unknown error')
            print(f"❌ Test failed: {error_msg}")
            print(f"📄 Report with input data saved: {report_file}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during AI test: {e}")
        return True


def handle_ai_usage_command(args: List[str]) -> bool:
    """Handle ai usage command - show AI usage statistics."""
    try:
        if args and args[0] == 'today':
            stats = database.get_ai_usage_stats(days=1)
            usage_text = ai.format_usage_stats(stats, "Today's")
        elif args and args[0] == 'month':
            stats = database.get_ai_usage_stats(days=30)
            usage_text = ai.format_usage_stats(stats, "Last 30 Days")
        else:
            stats = database.get_ai_usage_stats()
            usage_text = ai.format_usage_stats(stats, "Total")
        
        print(usage_text)
        
        return True
    except Exception as e:
        print(f"❌ Error getting AI usage stats: {e}")
        return True


def handle_tag_remove_command(args: List[str]) -> bool:
    """Handle tag remove command - blacklist a tag from current track."""
    global current_player_state, music_tracks
    
    if not args:
        print("Error: Please specify a tag to remove. Usage: tag remove <tag>")
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
    
    # Get track ID
    track_id = get_current_track_id()
    if not track_id:
        print("Could not find track in database")
        return True
    
    tag_name = ' '.join(args).lower()
    
    try:
        # Try to blacklist the tag
        if database.blacklist_tag(track_id, tag_name):
            print(f"🚫 Blacklisted tag '{tag_name}' from: {library.get_display_name(current_track)}")
            print("   This tag will not be suggested by AI for this track again")
        else:
            print(f"❌ Tag '{tag_name}' not found on this track")
    except Exception as e:
        print(f"❌ Error removing tag: {e}")
    
    return True


def handle_tag_list_command() -> bool:
    """Handle tag list command - show all tags for current track."""
    global current_player_state, music_tracks
    
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
    
    # Get track ID
    track_id = get_current_track_id()
    if not track_id:
        print("Could not find track in database")
        return True
    
    try:
        tags = database.get_track_tags(track_id, include_blacklisted=False)
        blacklisted_tags = database.get_track_tags(track_id, include_blacklisted=True)
        blacklisted_tags = [t for t in blacklisted_tags if t['blacklisted']]
        
        print(f"🏷️  Tags for: {library.get_display_name(current_track)}")
        
        if tags:
            # Group tags by source
            ai_tags = [t for t in tags if t['source'] == 'ai']
            user_tags = [t for t in tags if t['source'] == 'user']
            
            if ai_tags:
                print(f"   🤖 AI tags ({len(ai_tags)}): {', '.join(t['tag_name'] for t in ai_tags)}")
            
            if user_tags:
                print(f"   👤 User tags ({len(user_tags)}): {', '.join(t['tag_name'] for t in user_tags)}")
        else:
            print("   No tags found")
        
        if blacklisted_tags:
            print(f"   🚫 Blacklisted ({len(blacklisted_tags)}): {', '.join(t['tag_name'] for t in blacklisted_tags)}")
        
    except Exception as e:
        print(f"❌ Error getting tags: {e}")
    
    return True


def handle_playlist_list_command() -> bool:
    """Handle playlist command - list all playlists."""
    try:
        playlists = playlist.get_all_playlists()

        if not playlists:
            print("No playlists found. Create one with: playlist new manual <name>")
            return True

        # Check which one is active
        active = playlist.get_active_playlist()
        active_id = active['id'] if active else None

        print(f"\n📋 Playlists ({len(playlists)} total):")
        print("=" * 60)

        for pl in playlists:
            active_marker = " [ACTIVE]" if pl['id'] == active_id else ""
            type_emoji = "📝" if pl['type'] == 'manual' else "🤖"
            print(f"{type_emoji} {pl['name']}{active_marker}")
            print(f"   Type: {pl['type']} | Tracks: {pl['track_count']}")
            if pl['description']:
                print(f"   Description: {pl['description']}")
            print()

        return True
    except Exception as e:
        print(f"❌ Error listing playlists: {e}")
        return True


def smart_playlist_wizard(name: str) -> bool:
    """Interactive wizard for creating a smart playlist with filters.

    Args:
        name: Name of the playlist to create

    Returns:
        True to continue interactive loop
    """
    print(f"\n🧙 Smart Playlist Wizard: {name}")
    print("=" * 60)
    print("Create filters to automatically match tracks.\n")

    # Create the playlist first
    try:
        playlist_id = playlist.create_playlist(name, 'smart', description=None)
    except ValueError as e:
        print(f"❌ Error: {e}")
        return True

    filters_added = []

    # Loop to add filters
    while True:
        print("\n" + "-" * 60)
        print("Add a filter rule:")
        print()

        # Show valid fields
        print("Available fields:")
        print("  Text: title, artist, album, genre, key")
        print("  Numeric: year, bpm")
        print()

        # Get field
        field = input("Field (or 'done' to finish): ").strip().lower()

        if field == 'done':
            if not filters_added:
                print("❌ You must add at least one filter for a smart playlist")
                # Delete the empty playlist
                playlist.delete_playlist(playlist_id)
                return True
            break

        if field not in playlist_filters.VALID_FIELDS:
            print(f"❌ Invalid field. Must be one of: {', '.join(sorted(playlist_filters.VALID_FIELDS))}")
            continue

        # Show valid operators for this field
        if field in playlist_filters.NUMERIC_FIELDS:
            print(f"\nNumeric operators: {', '.join(sorted(playlist_filters.NUMERIC_OPERATORS))}")
            valid_ops = playlist_filters.NUMERIC_OPERATORS
        else:
            print(f"\nText operators: {', '.join(sorted(playlist_filters.TEXT_OPERATORS))}")
            valid_ops = playlist_filters.TEXT_OPERATORS

        # Get operator
        operator = input("Operator: ").strip().lower()

        if operator not in valid_ops:
            print(f"❌ Invalid operator for {field}. Must be one of: {', '.join(sorted(valid_ops))}")
            continue

        # Get value
        value = input("Value: ").strip()

        if not value:
            print("❌ Value cannot be empty")
            continue

        # Determine conjunction for next filter
        conjunction = 'AND'
        if filters_added:
            conj_input = input("Combine with previous filter using AND or OR? [AND]: ").strip().upper()
            if conj_input in ('AND', 'OR'):
                conjunction = conj_input

        # Add filter
        try:
            filter_id = playlist_filters.add_filter(playlist_id, field, operator, value, conjunction)
            filters_added.append({
                'id': filter_id,
                'field': field,
                'operator': operator,
                'value': value,
                'conjunction': conjunction
            })
            print(f"✅ Added filter: {field} {operator} '{value}'")
        except ValueError as e:
            print(f"❌ Error: {e}")
            continue

        # Ask if they want to add another
        more = input("\nAdd another filter? (y/n) [n]: ").strip().lower()
        if more != 'y':
            break

    # Preview matching tracks
    print("\n" + "=" * 60)
    print("📊 Preview: Finding matching tracks...")

    try:
        matching_tracks = playlist_filters.evaluate_filters(playlist_id)
        count = len(matching_tracks)

        print(f"\n✅ Found {count} matching tracks")

        if count > 0:
            print("\nFirst 10 matches:")
            for i, track in enumerate(matching_tracks[:10], 1):
                artist = track.get('artist', 'Unknown')
                title = track.get('title', 'Unknown')
                album = track.get('album', '')
                print(f"  {i}. {artist} - {title}")
                if album:
                    print(f"     Album: {album}")

        # Show filters
        print(f"\n📋 Filter rules for '{name}':")
        for i, f in enumerate(filters_added, 1):
            prefix = f"  {f['conjunction']}" if i > 1 else "  "
            print(f"{prefix} {f['field']} {f['operator']} '{f['value']}'")

        # Confirm
        print()
        confirm = input("Save this smart playlist? (y/n) [y]: ").strip().lower()

        if confirm == 'n':
            playlist.delete_playlist(playlist_id)
            print("❌ Smart playlist cancelled")
            return True

        # Update track count for the smart playlist
        playlist.update_playlist_track_count(playlist_id)

        print(f"\n✅ Created smart playlist: {name}")
        print(f"   {count} tracks match your filters")
        print(f"   Set as active with: playlist active \"{name}\"")

    except Exception as e:
        print(f"❌ Error evaluating filters: {e}")
        playlist.delete_playlist(playlist_id)
        return True

    return True


def handle_playlist_new_command(args: List[str]) -> bool:
    """Handle playlist new command - create a new playlist."""
    if len(args) < 2:
        print("Error: Please specify playlist type and name")
        print("Usage: playlist new manual <name>")
        print("       playlist new smart <name>")
        return True

    playlist_type = args[0].lower()
    if playlist_type not in ['manual', 'smart']:
        print(f"Error: Invalid playlist type '{playlist_type}'. Must be 'manual' or 'smart'")
        return True

    name = ' '.join(args[1:])

    # Smart playlist - launch wizard
    if playlist_type == 'smart':
        return smart_playlist_wizard(name)

    try:
        playlist_id = playlist.create_playlist(name, playlist_type, description=None)
        print(f"✅ Created {playlist_type} playlist: {name}")
        print(f"   Playlist ID: {playlist_id}")
        print(f"   Add tracks with: add \"{name}\"")
        return True
    except ValueError as e:
        print(f"❌ Error: {e}")
        return True
    except Exception as e:
        print(f"❌ Error creating playlist: {e}")
        return True


def handle_playlist_delete_command(args: List[str]) -> bool:
    """Handle playlist delete command - delete a playlist."""
    if not args:
        print("Error: Please specify playlist name")
        print("Usage: playlist delete <name>")
        return True

    name = ' '.join(args)
    pl = playlist.get_playlist_by_name(name)

    if not pl:
        print(f"❌ Playlist '{name}' not found")
        return True

    # Confirm deletion
    print(f"⚠️  Delete playlist '{name}'? This cannot be undone.")
    confirm = input("Type 'yes' to confirm: ").strip().lower()

    if confirm != 'yes':
        print("Deletion cancelled")
        return True

    try:
        if playlist.delete_playlist(pl['id']):
            print(f"✅ Deleted playlist: {name}")
        else:
            print(f"❌ Failed to delete playlist: {name}")
        return True
    except Exception as e:
        print(f"❌ Error deleting playlist: {e}")
        return True


def handle_playlist_rename_command(args: List[str]) -> bool:
    """Handle playlist rename command - rename a playlist."""
    if len(args) < 2:
        print("Error: Please specify old and new names")
        print('Usage: playlist rename "old name" "new name"')
        return True

    # Parse quoted args to handle multi-word playlist names
    parsed_args = parse_quoted_args(args)

    if len(parsed_args) < 2:
        print("Error: Please specify both old and new names")
        print('Usage: playlist rename "old name" "new name"')
        return True

    old_name = parsed_args[0]
    new_name = parsed_args[1]

    pl = playlist.get_playlist_by_name(old_name)
    if not pl:
        print(f"❌ Playlist '{old_name}' not found")
        return True

    try:
        if playlist.rename_playlist(pl['id'], new_name):
            print(f"✅ Renamed playlist: '{old_name}' → '{new_name}'")
        else:
            print(f"❌ Failed to rename playlist")
        return True
    except ValueError as e:
        print(f"❌ Error: {e}")
        return True
    except Exception as e:
        print(f"❌ Error renaming playlist: {e}")
        return True


def handle_playlist_show_command(args: List[str]) -> bool:
    """Handle playlist show command - show playlist details and tracks."""
    if not args:
        print("Error: Please specify playlist name")
        print("Usage: playlist show <name>")
        return True

    name = ' '.join(args)
    pl = playlist.get_playlist_by_name(name)

    if not pl:
        print(f"❌ Playlist '{name}' not found")
        return True

    try:
        tracks = playlist.get_playlist_tracks(pl['id'])

        print(f"\n📋 Playlist: {pl['name']}")
        print("=" * 60)
        print(f"Type: {pl['type']}")
        if pl['description']:
            print(f"Description: {pl['description']}")
        print(f"Created: {pl['created_at']}")
        print(f"Updated: {pl['updated_at']}")
        print(f"Tracks: {len(tracks)}")
        print()

        if not tracks:
            print("No tracks in this playlist")
            if pl['type'] == 'manual':
                print(f"Add tracks with: add \"{name}\"")
        else:
            print("Tracks:")
            for i, track in enumerate(tracks, 1):
                artist = track.get('artist') or 'Unknown'
                title = track.get('title') or 'Unknown'
                album = track.get('album', '')
                print(f"  {i}. {artist} - {title}")
                if album:
                    print(f"     Album: {album}")

        return True
    except Exception as e:
        print(f"❌ Error showing playlist: {e}")
        return True


def handle_playlist_active_command(args: List[str]) -> bool:
    """Handle playlist active command - set or clear active playlist."""
    if not args:
        # Show current active playlist
        active = playlist.get_active_playlist()
        if active:
            print(f"Active playlist: {active['name']}")
        else:
            print("No active playlist (playing all tracks)")
        return True

    name = ' '.join(args)

    if name.lower() == 'none':
        # Clear active playlist
        if playlist.clear_active_playlist():
            print("✅ Cleared active playlist (now playing all tracks)")
        else:
            print("No active playlist was set")
        return True

    # Set active playlist
    pl = playlist.get_playlist_by_name(name)
    if not pl:
        print(f"❌ Playlist '{name}' not found")
        return True

    try:
        if playlist.set_active_playlist(pl['id']):
            print(f"✅ Set active playlist: {name}")
            print(f"   Now playing only tracks from this playlist")
        else:
            print(f"❌ Failed to set active playlist")
        return True
    except Exception as e:
        print(f"❌ Error setting active playlist: {e}")
        return True


def handle_add_command(args: List[str]) -> bool:
    """Handle add command - add current track to playlist."""
    global current_player_state, music_tracks

    if not current_player_state.current_track:
        print("No track is currently playing")
        return True

    if not args:
        print("Error: Please specify playlist name")
        print("Usage: add <playlist_name>")
        return True

    name = ' '.join(args)
    pl = playlist.get_playlist_by_name(name)

    if not pl:
        print(f"❌ Playlist '{name}' not found")
        return True

    # Get current track ID
    track_id = get_current_track_id()
    if not track_id:
        print("❌ Could not find current track in database")
        return True

    try:
        if playlist.add_track_to_playlist(pl['id'], track_id):
            # Find current track info for display
            current_track = None
            for track in music_tracks:
                if track.file_path == current_player_state.current_track:
                    current_track = track
                    break

            if current_track:
                print(f"✅ Added to '{name}': {library.get_display_name(current_track)}")
            else:
                print(f"✅ Added current track to playlist: {name}")
        else:
            print(f"Track is already in playlist '{name}'")
        return True
    except ValueError as e:
        print(f"❌ Error: {e}")
        return True
    except Exception as e:
        print(f"❌ Error adding track to playlist: {e}")
        return True


def handle_remove_command(args: List[str]) -> bool:
    """Handle remove command - remove current track from playlist."""
    global current_player_state, music_tracks

    if not current_player_state.current_track:
        print("No track is currently playing")
        return True

    if not args:
        print("Error: Please specify playlist name")
        print("Usage: remove <playlist_name>")
        return True

    name = ' '.join(args)
    pl = playlist.get_playlist_by_name(name)

    if not pl:
        print(f"❌ Playlist '{name}' not found")
        return True

    # Get current track ID
    track_id = get_current_track_id()
    if not track_id:
        print("❌ Could not find current track in database")
        return True

    try:
        if playlist.remove_track_from_playlist(pl['id'], track_id):
            # Find current track info for display
            current_track = None
            for track in music_tracks:
                if track.file_path == current_player_state.current_track:
                    current_track = track
                    break

            if current_track:
                print(f"✅ Removed from '{name}': {library.get_display_name(current_track)}")
            else:
                print(f"✅ Removed current track from playlist: {name}")
        else:
            print(f"Track is not in playlist '{name}'")
        return True
    except ValueError as e:
        print(f"❌ Error: {e}")
        return True
    except Exception as e:
        print(f"❌ Error removing track from playlist: {e}")
        return True


def handle_command(command: str, args: List[str]) -> bool:
    """
    Handle a single command.
    
    Returns:
        True if the program should continue, False if it should exit
    """
    if command in ['quit', 'exit']:
        # Clean up MPV player before exiting
        global current_player_state
        if player.is_mpv_running(current_player_state):
            print("Stopping music player...")
            player.stop_mpv(current_player_state)
        print("Goodbye!")
        return False
    
    elif command == 'help':
        print_help()
    
    elif command == 'init':
        print("Initializing Music Minion configuration...")
        config.ensure_directories()
        cfg = config.load_config()
        print(f"Configuration loaded from: {config.get_config_path()}")
        print(f"Data directory: {config.get_data_dir()}")
        
        print("Setting up database...")
        database.init_database()
        print(f"Database initialized at: {database.get_database_path()}")
        
        print(f"Library paths: {cfg.music.library_paths}")
        print("Music Minion is ready to use!")
    
    elif command == 'play':
        return handle_play_command(args)
    
    elif command == 'pause':
        return handle_pause_command()
    
    elif command == 'resume':
        return handle_resume_command()
    
    elif command == 'skip':
        return handle_skip_command()
    
    elif command == 'stop':
        return handle_stop_command()
    
    elif command == 'killall':
        return handle_killall_command()
    
    elif command == 'archive':
        return handle_archive_command()
    
    elif command == 'like':
        return handle_like_command()
    
    elif command == 'love':
        return handle_love_command()
    
    elif command == 'note':
        return handle_note_command(args)
    
    elif command == 'status':
        return handle_status_command()
    
    elif command == 'stats':
        return handle_stats_command()
    
    elif command == 'scan':
        return handle_scan_command()

    elif command == 'migrate':
        print("Running database migrations...")
        database.init_database()
        print("✅ Database migrations complete")
        return True

    elif command == 'playlist':
        if not args:
            return handle_playlist_list_command()
        elif args[0] == 'new':
            return handle_playlist_new_command(args[1:])
        elif args[0] == 'delete':
            return handle_playlist_delete_command(args[1:])
        elif args[0] == 'rename':
            return handle_playlist_rename_command(args[1:])
        elif args[0] == 'show':
            return handle_playlist_show_command(args[1:])
        elif args[0] == 'active':
            return handle_playlist_active_command(args[1:])
        else:
            print(f"Unknown playlist subcommand: '{args[0]}'. Available: new, delete, rename, show, active")

    elif command == 'add':
        return handle_add_command(args)

    elif command == 'remove':
        return handle_remove_command(args)

    elif command == 'ai':
        if not args:
            print("Error: AI command requires a subcommand. Usage: ai <setup|analyze|test|usage>")
        elif args[0] == 'setup':
            return handle_ai_setup_command(args[1:])
        elif args[0] == 'analyze':
            return handle_ai_analyze_command()
        elif args[0] == 'test':
            return handle_ai_test_command()
        elif args[0] == 'usage':
            return handle_ai_usage_command(args[1:])
        else:
            print(f"Unknown AI subcommand: '{args[0]}'. Available: setup, analyze, test, usage")

    elif command == 'tag':
        if not args:
            print("Error: Tag command requires a subcommand. Usage: tag <remove|list>")
        elif args[0] == 'remove':
            return handle_tag_remove_command(args[1:])
        elif args[0] == 'list':
            return handle_tag_list_command()
        else:
            print(f"Unknown tag subcommand: '{args[0]}'. Available: remove, list")
    
    elif command == '':
        # Empty command, do nothing
        pass
    
    else:
        print(f"Unknown command: '{command}'. Type 'help' for available commands.")
    
    return True


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
    console.print("Type 'help' for available commands, or 'quit' to exit.")
    console.print()
    
    # Start background dashboard updater
    updater_thread = threading.Thread(target=dashboard_updater, daemon=True)
    updater_thread.start()
    
    try:
        while True:
            try:
                user_input = input("music-minion> ").strip()
                command, args = parse_command(user_input)
                
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
                
                if not handle_command(command, args):
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


def interactive_mode() -> None:
    """Run the interactive command loop."""
    global current_config

    # Load config if not already loaded
    if not current_config.music.library_paths:
        current_config = config.load_config()

    # Run database migrations on startup
    database.init_database()

    # Check if dashboard is enabled and Rich is available
    if current_config.ui.enable_dashboard:
        try:
            from rich.console import Console
            # Use dashboard mode if Rich is available (don't require terminal detection)
            interactive_mode_with_dashboard()
            return
        except ImportError:
            # Rich not available, fall back to simple mode
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
                command, args = parse_command(user_input)
                
                if not handle_command(command, args):
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