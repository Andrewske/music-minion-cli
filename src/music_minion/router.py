"""
Command routing for Music Minion CLI.

Routes user commands to appropriate handler functions.
"""

from typing import List, Tuple

from music_minion.context import AppContext
from music_minion.core import config
from music_minion.core import database
from music_minion.domain import playback as playback_domain

# Import command handlers
from music_minion.commands import playback
from music_minion.commands import rating
from music_minion.commands import admin
from music_minion.commands import ai
from music_minion.commands import sync
from music_minion.commands import playlist
from music_minion.commands import track


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
  playlist none                   Clear active playlist (shorthand)
  playlist import <file>          Import playlist from M3U/M3U8/Serato crate
  playlist export <name> [format] Export playlist (m3u8/crate/all, default: m3u8)
  add <playlist>                  Add current track to playlist
  remove <playlist>               Remove current track from playlist

AI Commands:
  ai setup <key>    Set up OpenAI API key for AI analysis
  ai analyze        Analyze current track with AI and add tags
  ai review         Review and improve tags for current track (conversational)
  ai enhance prompt Improve tagging prompt based on accumulated learnings
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


def handle_command(ctx: AppContext, command: str, args: List[str]) -> Tuple[AppContext, bool]:
    """
    Handle a single command with explicit state passing.

    Args:
        ctx: Application context
        command: Command name
        args: Command arguments

    Returns:
        (updated_context, should_continue) - Updated context and whether to continue
    """
    if command in ['quit', 'exit']:
        # Clean up MPV player before exiting
        if playback_domain.is_mpv_running(ctx.player_state):
            print("Stopping music playback...")
            playback_domain.stop_mpv(ctx.player_state)
        print("Goodbye!")
        return ctx, False

    elif command == 'help':
        print_help()
        return ctx, True

    elif command == 'init':
        return admin.handle_init_command(ctx)

    elif command == 'play':
        return playback.handle_play_command(ctx, args)

    elif command == 'pause':
        return playback.handle_pause_command(ctx)

    elif command == 'resume':
        return playback.handle_resume_command(ctx)

    elif command == 'skip':
        return playback.handle_skip_command(ctx)

    elif command == 'shuffle':
        return playback.handle_shuffle_command(ctx, args)

    elif command == 'stop':
        return playback.handle_stop_command(ctx)

    elif command == 'killall':
        return admin.handle_killall_command(ctx)

    elif command == 'archive':
        return rating.handle_archive_command(ctx)

    elif command == 'like':
        return rating.handle_like_command(ctx)

    elif command == 'love':
        return rating.handle_love_command(ctx)

    elif command == 'note':
        return rating.handle_note_command(ctx, args)

    elif command == 'status':
        return playback.handle_status_command(ctx)

    elif command == 'stats':
        return admin.handle_stats_command(ctx)

    elif command == 'scan':
        return admin.handle_scan_command(ctx)

    elif command == 'migrate':
        return admin.handle_migrate_command(ctx)

    elif command == 'playlist':
        if not args:
            return playlist.handle_playlist_list_command(ctx)
        elif args[0] == 'none':
            return playlist.handle_playlist_active_command(ctx, ['none'])
        elif args[0] == 'new':
            return playlist.handle_playlist_new_command(ctx, args[1:])
        elif args[0] == 'delete':
            return playlist.handle_playlist_delete_command(ctx, args[1:])
        elif args[0] == 'rename':
            return playlist.handle_playlist_rename_command(ctx, args[1:])
        elif args[0] == 'show':
            return playlist.handle_playlist_show_command(ctx, args[1:])
        elif args[0] == 'active':
            return playlist.handle_playlist_active_command(ctx, args[1:])
        elif args[0] == 'import':
            return playlist.handle_playlist_import_command(ctx, args[1:])
        elif args[0] == 'export':
            return playlist.handle_playlist_export_command(ctx, args[1:])
        else:
            print(f"Unknown playlist subcommand: '{args[0]}'. Available: new, delete, rename, show, active, none, import, export")
            return ctx, True

    elif command == 'add':
        return track.handle_add_command(ctx, args)

    elif command == 'remove':
        return track.handle_remove_command(ctx, args)

    elif command == 'ai':
        if not args:
            print("Error: AI command requires a subcommand. Usage: ai <setup|analyze|review|enhance|test|usage>")
            return ctx, True
        elif args[0] == 'setup':
            return ai.handle_ai_setup_command(ctx, args[1:])
        elif args[0] == 'analyze':
            return ai.handle_ai_analyze_command(ctx)
        elif args[0] == 'review':
            return ai.handle_ai_review_command(ctx)
        elif args[0] == 'enhance':
            return ai.handle_ai_enhance_command(ctx, args[1:])
        elif args[0] == 'test':
            return ai.handle_ai_test_command(ctx)
        elif args[0] == 'usage':
            return ai.handle_ai_usage_command(ctx, args[1:])
        else:
            print(f"Unknown AI subcommand: '{args[0]}'. Available: setup, analyze, review, enhance, test, usage")
            return ctx, True

    elif command == 'tag':
        if not args:
            print("Error: Tag command requires a subcommand. Usage: tag <remove|list>")
            return ctx, True
        elif args[0] == 'remove':
            return admin.handle_tag_remove_command(ctx, args[1:])
        elif args[0] == 'list':
            return admin.handle_tag_list_command(ctx)
        else:
            print(f"Unknown tag subcommand: '{args[0]}'. Available: remove, list")
            return ctx, True

    elif command == 'sync':
        if not args:
            print("Error: Sync command requires a subcommand. Usage: sync <export|import|status|rescan>")
            return ctx, True
        elif args[0] == 'export':
            return sync.handle_sync_export_command(ctx)
        elif args[0] == 'import':
            return sync.handle_sync_import_command(ctx, args[1:])
        elif args[0] == 'status':
            return sync.handle_sync_status_command(ctx)
        elif args[0] == 'rescan':
            return sync.handle_sync_rescan_command(ctx, args[1:])
        else:
            print(f"Unknown sync subcommand: '{args[0]}'. Available: export, import, status, rescan")
            return ctx, True

    elif command == '':
        # Empty command, do nothing
        return ctx, True

    else:
        print(f"Unknown command: '{command}'. Type 'help' for available commands.")
        return ctx, True
