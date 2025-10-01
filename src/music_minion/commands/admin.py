"""
Admin command handlers for Music Minion CLI.

Handles: init, scan, migrate, killall, stats, tag (remove/list)
"""

import subprocess
import glob
import os
from typing import List

from ..core import config
from ..core import database
from .. import library


def get_player_state():
    """Get current player state from main module."""
    from .. import main
    return main.current_player_state


def get_music_tracks():
    """Get music tracks from main module."""
    from .. import main
    return main.music_tracks


def get_current_track_id():
    """Get current track database ID."""
    from .. import main
    return main.get_current_track_id()


def handle_init_command() -> bool:
    """Handle init command - initialize Music Minion configuration."""
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
    return True


def handle_killall_command() -> bool:
    """Kill all MPV processes (emergency stop)."""
    try:
        result = subprocess.run(['pkill', 'mpv'], capture_output=True)
        if result.returncode == 0:
            print("⛔ Killed all MPV processes")
        else:
            print("No MPV processes found")

        # Clean up any leftover sockets
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

        if analytics['top_rated_tracks']:
            print("\n🌟 Top Rated Tracks:")
            for track_data in analytics['top_rated_tracks'][:10]:
                track_info = f"{track_data['artist']} - {track_data['title']}" if track_data['artist'] else track_data['title']
                print(f"  {track_data['rating_count']} ratings: {track_info}")

        return True
    except Exception as e:
        print(f"❌ Error getting statistics: {e}")
        return True


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


def handle_migrate_command() -> bool:
    """Handle migrate command - run database migrations."""
    print("Running database migrations...")
    database.init_database()
    print("✅ Database migrations complete")
    return True


def handle_tag_remove_command(args: List[str]) -> bool:
    """Handle tag remove command - blacklist a tag from current track."""
    current_player_state = get_player_state()
    music_tracks = get_music_tracks()

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
    current_player_state = get_player_state()
    music_tracks = get_music_tracks()

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
