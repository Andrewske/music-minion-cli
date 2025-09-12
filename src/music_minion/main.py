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

# Global state for interactive mode
current_player_state: player.PlayerState = player.PlayerState()
music_tracks: List[library.Track] = []
current_config: config.Config = config.Config()


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
  init              Initialize configuration and scan library
  help              Show this help message
  quit, exit        Exit the program

Interactive mode:
  Just run 'music-minion' to enter interactive mode where you can
  type commands directly.

Examples:
  play                    # Play random song
  play daft punk          # Search and play Daft Punk track
  play Am                 # Play track in A minor key
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
        print("Loading music library...")
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
            print(f"Loaded {len(music_tracks)} tracks from database")
        
        # If no database tracks or very few, fall back to filesystem scan
        if not music_tracks:
            print("No tracks in database, scanning filesystem...")
            music_tracks = library.scan_music_library(current_config, show_progress=False)
            
            if not music_tracks:
                print("No music files found in configured library paths.")
                print("Run 'music-minion scan' to populate the database, or 'music-minion init' to set up library paths.")
                return False
            
            print(f"Scanned {len(music_tracks)} tracks from filesystem")
    
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
                print("Resumed playback")
            else:
                print("Failed to resume playback")
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
        print(f"♪ Now playing: {library.get_display_name(track)}")
        if track.duration:
            print(f"   Duration: {library.get_duration_str(track)}")
        
        dj_info = library.get_dj_info(track)
        if dj_info != "No DJ metadata":
            print(f"   {dj_info}")
        
        # Store track in database
        track_id = database.get_or_create_track(
            track.file_path, track.title, track.artist, track.album,
            track.genre, track.year, track.duration, track.key, track.bpm
        )
        
        # Start playback session
        database.start_playback_session(track_id)
    else:
        print("Failed to play track")
    
    return True


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
    """Get tracks that are available for playback (not archived)."""
    global music_tracks
    
    if not music_tracks:
        return []
    
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
    
    # Library stats
    if music_tracks:
        print(f"📚 Library: {len(music_tracks)} tracks loaded")
    
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


def handle_command(command: str, args: List[str]) -> bool:
    """
    Handle a single command.
    
    Returns:
        True if the program should continue, False if it should exit
    """
    if command in ['quit', 'exit']:
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
    
    elif command == '':
        # Empty command, do nothing
        pass
    
    else:
        print(f"Unknown command: '{command}'. Type 'help' for available commands.")
    
    return True


def interactive_mode() -> None:
    """Run the interactive command loop."""
    print("Welcome to Music Minion CLI!")
    print("Type 'help' for available commands, or 'quit' to exit.")
    print()
    
    try:
        while True:
            try:
                user_input = input("music-minion> ").strip()
                command, args = parse_command(user_input)
                
                if not handle_command(command, args):
                    break
                    
            except KeyboardInterrupt:
                print("\nUse 'quit' or 'exit' to leave gracefully.")
            except EOFError:
                print("\nGoodbye!")
                break
                
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
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