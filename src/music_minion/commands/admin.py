"""
Admin command handlers for Music Minion CLI.

Handles: init, scan, migrate, killall, stats, tag (remove/list)
"""

import glob
import os
import subprocess
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from music_minion.context import AppContext
from music_minion.core import config, database
from music_minion.core.output import log
from music_minion.domain import library

# Global scan state (thread-safe)
_scan_state_lock = threading.Lock()
_scan_state: Optional[Dict[str, Any]] = None


def get_scan_state() -> Optional[Dict[str, Any]]:
    """Get current scan state (thread-safe)."""
    with _scan_state_lock:
        return _scan_state.copy() if _scan_state else None


def _update_scan_state(updates: Dict[str, Any]) -> None:
    """Update scan state (thread-safe, internal use only)."""
    global _scan_state
    with _scan_state_lock:
        if _scan_state is None:
            _scan_state = {}
        _scan_state.update(updates)


def _clear_scan_state() -> None:
    """Clear scan state (thread-safe, internal use only)."""
    global _scan_state
    with _scan_state_lock:
        _scan_state = None


def _count_music_files(cfg: config.Config) -> int:
    """Count total music files before scanning."""
    total = 0
    for library_path in cfg.music.library_paths:
        path = Path(library_path).expanduser()
        if not path.exists():
            continue

        try:
            if cfg.music.scan_recursive:
                files = path.rglob("*")
            else:
                files = path.iterdir()

            for local_path in files:
                if (
                    local_path.is_file()
                    and local_path.suffix.lower() in cfg.music.supported_formats
                ):
                    total += 1
        except (PermissionError, Exception):
            # Silently skip inaccessible directories
            pass

    return total


def _threaded_scan_worker(ctx: AppContext) -> None:
    """Background worker thread for library scanning."""
    try:
        # Initialize state
        _update_scan_state(
            {
                "phase": "counting",
                "files_scanned": 0,
                "total_files": 0,
                "current_file": "",
                "error": None,
                "completed": False,
                "tracks": [],
                "added": 0,
                "updated": 0,
                "errors": 0,
            }
        )

        # Count files first
        total_files = _count_music_files(ctx.config)
        _update_scan_state({"total_files": total_files, "phase": "scanning"})

        # Progress callback for scan
        files_scanned = 0

        def progress_callback(local_path: str, track) -> None:
            nonlocal files_scanned
            files_scanned += 1
            _update_scan_state(
                {"files_scanned": files_scanned, "current_file": Path(local_path).name}
            )

        # Scan library with progress
        tracks = library.scan_music_library(
            ctx.config, show_progress=False, progress_callback=progress_callback
        )

        if not tracks:
            _update_scan_state(
                {
                    "completed": True,
                    "error": "No music files found in configured library paths",
                }
            )
            return

        # Database phase (batch operation for performance)
        _update_scan_state({"phase": "database", "current_file": ""})

        try:
            added, updated = database.batch_upsert_tracks(tracks)
            errors = 0
        except Exception:
            added = 0
            updated = 0
            errors = len(tracks)

        # Compute stats
        stats = library.get_library_stats(tracks)

        # Mark complete
        _update_scan_state(
            {
                "completed": True,
                "tracks": tracks,
                "added": added,
                "updated": updated,
                "errors": errors,
                "stats": stats,
            }
        )

    except Exception as e:
        _update_scan_state(
            {
                "completed": True,
                "error": str(e),
            }
        )


def start_background_scan(ctx: AppContext) -> None:
    """Start library scan in background thread."""
    # Clear any previous scan state
    _clear_scan_state()

    # Start worker thread
    thread = threading.Thread(target=_threaded_scan_worker, args=(ctx,), daemon=True)
    thread.start()


def handle_init_command(ctx: AppContext) -> Tuple[AppContext, bool]:
    """Handle init command - initialize Music Minion configuration.

    Args:
        ctx: Application context

    Returns:
        (updated_context, should_continue)
    """
    log("Initializing Music Minion configuration...")
    config.ensure_directories()
    cfg = config.load_config()
    log(f"Configuration loaded from: {config.get_config_path()}")
    log(f"Data directory: {config.get_data_dir()}")

    log("Setting up database...")
    database.init_database()
    log(f"Database initialized at: {database.get_database_path()}")

    log(f"Library paths: {cfg.music.library_paths}")
    log("Music Minion is ready to use!")

    # Update context with loaded config
    ctx = ctx.with_config(cfg)
    return ctx, True


def handle_killall_command(ctx: AppContext) -> Tuple[AppContext, bool]:
    """Kill all MPV processes (emergency stop).

    Args:
        ctx: Application context

    Returns:
        (updated_context, should_continue)
    """
    try:
        result = subprocess.run(["pkill", "mpv"], capture_output=True)
        if result.returncode == 0:
            log("⛔ Killed all MPV processes")
        else:
            log("No MPV processes found")

        # Clean up any leftover sockets
        sockets = glob.glob("/tmp/mpv-socket-*")
        for socket in sockets:
            try:
                os.unlink(socket)
            except OSError:
                pass
        if sockets:
            log(f"Cleaned up {len(sockets)} leftover socket(s)")

    except Exception as e:
        log(f"Error killing MPV: {e}", level="error")

    return ctx, True


def handle_stats_command(ctx: AppContext) -> Tuple[AppContext, bool]:
    """Handle stats command - show database statistics.

    Args:
        ctx: Application context

    Returns:
        (updated_context, should_continue)
    """
    try:
        analytics = database.get_library_analytics()

        log("\n📊 Library Statistics")
        log("=" * 40)
        log(f"Total tracks: {analytics['total_tracks']}")
        log(f"Rated tracks: {analytics['rated_tracks']}")
        log(f"Total ratings: {analytics['total_ratings']}")

        if analytics["rating_distribution"]:
            log("\n📈 Rating Distribution:")
            for rating_type, count in analytics["rating_distribution"].items():
                emoji = {"archive": "📦", "skip": "⏭️", "like": "👍", "love": "❤️"}.get(
                    rating_type, "❓"
                )
                log(f"  {emoji} {rating_type}: {count}")

        if analytics["top_rated_tracks"]:
            log("\n🌟 Top Rated Tracks:")
            for track_data in analytics["top_rated_tracks"][:10]:
                track_info = (
                    f"{track_data['artist']} - {track_data['title']}"
                    if track_data["artist"]
                    else track_data["title"]
                )
                log(f"  {track_data['rating_count']} ratings: {track_info}")

        return ctx, True
    except Exception as e:
        log(f"❌ Error getting statistics: {e}", level="error")
        return ctx, True


def handle_scan_command(ctx: AppContext) -> Tuple[AppContext, bool]:
    """Handle scan command - scan library and populate database.

    Args:
        ctx: Application context

    Returns:
        (updated_context, should_continue)
    """
    log("🔍 Starting library scan...")

    try:
        # Scan library
        tracks = library.scan_music_library(ctx.config, show_progress=True)

        if not tracks:
            log("❌ No music files found in configured library paths", level="warning")
            return ctx, True

        # Add all tracks to database (batch operation for performance)
        log(f"\n💾 Adding {len(tracks)} tracks to database...")
        try:
            added, updated = database.batch_upsert_tracks(tracks)
            errors = 0
        except Exception as e:
            log(f"  Error batch processing tracks: {e}", level="error")
            errors = len(tracks)
            added = 0
            updated = 0

        # Show scan results
        log("\n✅ Scan complete!")
        log(f"  📝 New tracks: {added}")
        log(f"  🔄 Updated tracks: {updated}")
        if errors:
            log(f"  ⚠️  Errors: {errors}", level="warning")

        # Show library stats
        stats = library.get_library_stats(tracks)
        log("\n📚 Library Overview:")
        log(f"  Total duration: {stats['total_duration_str']}")
        log(f"  Total size: {stats['total_size_str']}")
        log(f"  Artists: {stats['artists']}")
        log(f"  Albums: {stats['albums']}")

        if stats["formats"]:
            log("\n📂 Formats:")
            for fmt, count in sorted(
                stats["formats"].items(), key=lambda x: x[1], reverse=True
            ):
                log(f"  {fmt}: {count} files")

        if stats["avg_bpm"]:
            log("\n🎵 DJ Metadata:")
            log(f"  Tracks with BPM: {stats['tracks_with_bpm']}")
            log(f"  Average BPM: {stats['avg_bpm']:.1f}")
            log(f"  Tracks with key: {stats['tracks_with_key']}")

        # Update context with scanned tracks
        ctx = ctx.with_tracks(tracks)
        return ctx, True

    except Exception as e:
        log(f"❌ Error scanning library: {e}", level="error")
        import traceback

        traceback.print_exc()
        return ctx, False


def handle_migrate_command(ctx: AppContext) -> Tuple[AppContext, bool]:
    """Handle migrate command - run database migrations.

    Args:
        ctx: Application context

    Returns:
        (updated_context, should_continue)
    """
    log("Running database migrations...")
    database.init_database()
    log("✅ Database migrations complete")
    return ctx, True


def handle_tag_remove_command(
    ctx: AppContext, args: List[str]
) -> Tuple[AppContext, bool]:
    """Handle tag remove command - blacklist a tag from current track.

    Args:
        ctx: Application context
        args: Command arguments

    Returns:
        (updated_context, should_continue)
    """
    if not args:
        log(
            "Error: Please specify a tag to remove. Usage: tag remove <tag>",
            level="warning",
        )
        return ctx, True

    if not ctx.player_state.current_track:
        log("No track is currently playing", level="warning")
        return ctx, True

    # Get track ID from player state (works for both local and streaming tracks)
    track_id = ctx.player_state.current_track_id

    # Fallback to path lookup for backward compatibility
    if not track_id:
        db_track = database.get_track_by_path(ctx.player_state.current_track)
        if not db_track:
            log("❌ Could not find current track in database", level="error")
            return ctx, True
        track_id = db_track["id"]

    # Get full track info from database
    db_track = database.get_track_by_id(track_id)
    if not db_track:
        log("❌ Could not find current track in database", level="error")
        return ctx, True

    # Find Track object in memory for display (multi-source lookup)
    current_track = None
    for track in ctx.music_tracks:
        if (
            (track.local_path and track.local_path == db_track.get("local_path"))
            or (
                track.soundcloud_id
                and track.soundcloud_id == db_track.get("soundcloud_id")
            )
            or (track.spotify_id and track.spotify_id == db_track.get("spotify_id"))
            or (track.youtube_id and track.youtube_id == db_track.get("youtube_id"))
        ):
            current_track = track
            break

    if not current_track:
        log("Could not find current track information", level="warning")
        return ctx, True

    tag_name = " ".join(args).lower()

    try:
        # Try to blacklist the tag
        if database.blacklist_tag(track_id, tag_name):
            log(
                f"🚫 Blacklisted tag '{tag_name}' from: {library.get_display_name(current_track)}"
            )
            log("   This tag will not be suggested by AI for this track again")
        else:
            log(f"❌ Tag '{tag_name}' not found on this track", level="warning")
    except Exception as e:
        log(f"❌ Error removing tag: {e}", level="error")

    return ctx, True


def handle_tag_list_command(ctx: AppContext) -> Tuple[AppContext, bool]:
    """Handle tag list command - show all tags for current track.

    Args:
        ctx: Application context

    Returns:
        (updated_context, should_continue)
    """
    if not ctx.player_state.current_track:
        log("No track is currently playing", level="warning")
        return ctx, True

    # Get track ID from player state (works for both local and streaming tracks)
    track_id = ctx.player_state.current_track_id

    # Fallback to path lookup for backward compatibility
    if not track_id:
        db_track = database.get_track_by_path(ctx.player_state.current_track)
        if not db_track:
            log("❌ Could not find current track in database", level="error")
            return ctx, True
        track_id = db_track["id"]

    # Get full track info from database
    db_track = database.get_track_by_id(track_id)
    if not db_track:
        log("❌ Could not find current track in database", level="error")
        return ctx, True

    # Find Track object in memory for display (multi-source lookup)
    current_track = None
    for track in ctx.music_tracks:
        if (
            (track.local_path and track.local_path == db_track.get("local_path"))
            or (
                track.soundcloud_id
                and track.soundcloud_id == db_track.get("soundcloud_id")
            )
            or (track.spotify_id and track.spotify_id == db_track.get("spotify_id"))
            or (track.youtube_id and track.youtube_id == db_track.get("youtube_id"))
        ):
            current_track = track
            break

    if not current_track:
        log("Could not find current track information", level="warning")
        return ctx, True

    try:
        tags = database.get_track_tags(track_id, include_blacklisted=False)
        blacklisted_tags = database.get_track_tags(track_id, include_blacklisted=True)
        blacklisted_tags = [t for t in blacklisted_tags if t["blacklisted"]]

        log(f"🏷️  Tags for: {library.get_display_name(current_track)}")

        if tags:
            # Group tags by source
            ai_tags = [t for t in tags if t["source"] == "ai"]
            user_tags = [t for t in tags if t["source"] == "user"]

            if ai_tags:
                log(
                    f"   🤖 AI tags ({len(ai_tags)}): {', '.join(t['tag_name'] for t in ai_tags)}"
                )

            if user_tags:
                log(
                    f"   👤 User tags ({len(user_tags)}): {', '.join(t['tag_name'] for t in user_tags)}"
                )
        else:
            log("   No tags found")

        if blacklisted_tags:
            log(
                f"   🚫 Blacklisted ({len(blacklisted_tags)}): {', '.join(t['tag_name'] for t in blacklisted_tags)}"
            )

    except Exception as e:
        log(f"❌ Error getting tags: {e}", level="error")

    return ctx, True
