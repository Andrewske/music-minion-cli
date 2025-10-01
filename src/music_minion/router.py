"""
Command routing for Music Minion CLI.

Routes user commands to appropriate handler functions.
"""

from typing import List

from .core import config
from .core import database
from . import player

# Import command handlers
from .commands import playback
from .commands import rating
from .commands import admin
from .commands import ai_ops
from .commands import sync_ops
from .commands import playlist_ops
from .commands import track_ops


def print_help() -> None:
    """Display help information for available commands."""
    help_text = """
Music Minion CLI - Contextual Music Curation

Available commands:
  play [query]      Start playing music (random if no query, or search)
  pause             Pause current playback
  resume            Resume paused playback
  skip              Skip to next song
  shuffle           Show current shuffle mode
  shuffle on        Enable shuffle mode (random playback)
  shuffle off       Enable sequential mode (play in order)
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
  playlist new smart ai <n> "<d>" Create AI smart playlist (natural language)
  playlist delete <name>          Delete playlist
  playlist rename "old" "new"     Rename playlist (use quotes)
  playlist show <name>            Show playlist tracks
  playlist active <name>          Set active playlist
  playlist active none            Clear active playlist
  playlist import <file>          Import playlist from M3U/M3U8/Serato crate
  playlist export <name> [format] Export playlist (m3u8/crate/all, default: m3u8)
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

Sync Commands:
  sync export       Write all database tags to file metadata
  sync import       Read tags from changed files to database
  sync import --all Import from all files (force full import)
  sync status       Show sync status and pending changes
  sync rescan       Rescan library for file changes (incremental)
  sync rescan --full Full library rescan (all files)

  init              Initialize configuration and scan library
  help              Show this help message
  quit, exit        Exit the program

Interactive mode:
  Just run 'music-minion' to enter interactive mode where you can
  type commands directly.

Advanced Features:
  /                       Command palette - browse all commands by category
  Tab                     Autocomplete commands and playlist names
  Ctrl+C                  Cancel current operation

Examples:
  play                    # Play random song
  play daft punk          # Search and play Daft Punk track
  playlist                # Browse playlists with fuzzy search
  /                       # Open command palette
  playlist new manual "NYE 2025"  # Create playlist
  add "NYE 2025"          # Add current track to playlist
"""
    print(help_text.strip())


def handle_command(command: str, args: List[str]) -> bool:
    """
    Handle a single command.

    Returns:
        True if the program should continue, False if it should exit
    """
    if command in ['quit', 'exit']:
        # Clean up MPV player before exiting
        from . import main
        if player.is_mpv_running(main.current_player_state):
            print("Stopping music player...")
            player.stop_mpv(main.current_player_state)
        print("Goodbye!")
        return False

    elif command == 'help':
        print_help()

    elif command == 'init':
        return admin.handle_init_command()

    elif command == 'play':
        return playback.handle_play_command(args)

    elif command == 'pause':
        return playback.handle_pause_command()

    elif command == 'resume':
        return playback.handle_resume_command()

    elif command == 'skip':
        return playback.handle_skip_command()

    elif command == 'shuffle':
        return playback.handle_shuffle_command(args)

    elif command == 'stop':
        return playback.handle_stop_command()

    elif command == 'killall':
        return admin.handle_killall_command()

    elif command == 'archive':
        return rating.handle_archive_command()

    elif command == 'like':
        return rating.handle_like_command()

    elif command == 'love':
        return rating.handle_love_command()

    elif command == 'note':
        return rating.handle_note_command(args)

    elif command == 'status':
        return playback.handle_status_command()

    elif command == 'stats':
        return admin.handle_stats_command()

    elif command == 'scan':
        return admin.handle_scan_command()

    elif command == 'migrate':
        return admin.handle_migrate_command()

    elif command == 'playlist':
        if not args:
            return playlist_ops.handle_playlist_list_command()
        elif args[0] == 'new':
            return playlist_ops.handle_playlist_new_command(args[1:])
        elif args[0] == 'delete':
            return playlist_ops.handle_playlist_delete_command(args[1:])
        elif args[0] == 'rename':
            return playlist_ops.handle_playlist_rename_command(args[1:])
        elif args[0] == 'show':
            return playlist_ops.handle_playlist_show_command(args[1:])
        elif args[0] == 'active':
            return playlist_ops.handle_playlist_active_command(args[1:])
        elif args[0] == 'import':
            return playlist_ops.handle_playlist_import_command(args[1:])
        elif args[0] == 'export':
            return playlist_ops.handle_playlist_export_command(args[1:])
        else:
            print(f"Unknown playlist subcommand: '{args[0]}'. Available: new, delete, rename, show, active, import, export")

    elif command == 'add':
        return track_ops.handle_add_command(args)

    elif command == 'remove':
        return track_ops.handle_remove_command(args)

    elif command == 'ai':
        if not args:
            print("Error: AI command requires a subcommand. Usage: ai <setup|analyze|test|usage>")
        elif args[0] == 'setup':
            return ai_ops.handle_ai_setup_command(args[1:])
        elif args[0] == 'analyze':
            return ai_ops.handle_ai_analyze_command()
        elif args[0] == 'test':
            return ai_ops.handle_ai_test_command()
        elif args[0] == 'usage':
            return ai_ops.handle_ai_usage_command(args[1:])
        else:
            print(f"Unknown AI subcommand: '{args[0]}'. Available: setup, analyze, test, usage")

    elif command == 'tag':
        if not args:
            print("Error: Tag command requires a subcommand. Usage: tag <remove|list>")
        elif args[0] == 'remove':
            return admin.handle_tag_remove_command(args[1:])
        elif args[0] == 'list':
            return admin.handle_tag_list_command()
        else:
            print(f"Unknown tag subcommand: '{args[0]}'. Available: remove, list")

    elif command == 'sync':
        if not args:
            print("Error: Sync command requires a subcommand. Usage: sync <export|import|status|rescan>")
        elif args[0] == 'export':
            return sync_ops.handle_sync_export_command()
        elif args[0] == 'import':
            return sync_ops.handle_sync_import_command(args[1:])
        elif args[0] == 'status':
            return sync_ops.handle_sync_status_command()
        elif args[0] == 'rescan':
            return sync_ops.handle_sync_rescan_command(args[1:])
        else:
            print(f"Unknown sync subcommand: '{args[0]}'. Available: export, import, status, rescan")

    elif command == '':
        # Empty command, do nothing
        pass

    else:
        print(f"Unknown command: '{command}'. Type 'help' for available commands.")

    return True
