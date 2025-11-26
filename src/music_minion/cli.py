"""
Music Minion CLI - Entry point with IPC support

This module serves as the CLI entry point, supporting both interactive mode
and IPC commands for hotkey integration.
"""

import argparse
import sys
import os
from music_minion import ipc


def run_locate_opus(folder: str, apply: bool = False) -> int:
    """Run the locate-opus utility to match opus files to MP3 records.

    Args:
        folder: Path to folder containing opus files
        apply: If True, update database; if False, dry run only

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    from music_minion.domain.library.locate_opus import locate_opus_replacements

    dry_run = not apply

    print(f"{'DRY RUN - ' if dry_run else ''}Locating opus replacements in: {folder}")
    print()

    try:
        result = locate_opus_replacements(folder, dry_run=dry_run)

        # Print results
        if result.updated:
            print(f"{'Would update' if dry_run else 'Updated'}: {len(result.updated)} tracks")
            for item in result.updated:
                tier = item.get("match_tier", "?")
                reason = item.get("match_reason", "unknown")
                score = item.get("match_score")
                score_str = f" ({score:.0%})" if score else ""
                print(f"  ✓ {item['opus_stem']}")
                print(f"    → Track #{item['matched_track_id']}: {item.get('matched_title', 'Unknown')}")
                print(f"    Match: Tier {tier} ({reason}){score_str}")
            print()

        if result.multiple_matches:
            print(f"Multiple matches (needs manual review): {len(result.multiple_matches)}")
            for item in result.multiple_matches:
                tier = item.get("match_tier", "?")
                print(f"  ⚠ {item['opus_stem']}")
                print(f"    Opus title: {item.get('opus_title', 'Unknown')}")
                print(f"    Tier {tier} found {len(item.get('matches', []))} matches:")
                for match in item.get("matches", [])[:3]:
                    score = match.get("score")
                    score_str = f" ({score:.0%})" if score else ""
                    print(f"      - #{match['id']}: {match.get('title', 'Unknown')}{score_str}")
            print()

        if result.no_match:
            print(f"No match found: {len(result.no_match)}")
            for item in result.no_match:
                print(f"  ✗ {item['opus_stem']}")
                print(f"    Title: {item.get('opus_title', 'Unknown')}")
                print(f"    Reason: {item.get('reason', 'unknown')}")
            print()

        # Summary
        total = len(result.updated) + len(result.multiple_matches) + len(result.no_match)
        print("=" * 50)
        print(f"Total opus files: {total}")
        print(f"  Matched:   {len(result.updated)}")
        print(f"  Ambiguous: {len(result.multiple_matches)}")
        print(f"  No match:  {len(result.no_match)}")

        if dry_run and result.updated:
            print()
            print("Run with --apply to update the database")

        return 0

    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


def send_ipc_command(command: str, args: list) -> int:
    """
    Send a command to running Music Minion instance via IPC.

    Args:
        command: Command name
        args: Command arguments

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    success, message = ipc.send_command(command, args)

    # Server handles notifications - no client-side notifications to avoid duplicates

    # Print message to stdout/stderr
    if success:
        print(message)
        return 0
    else:
        print(message, file=sys.stderr)
        return 1


def main() -> None:
    """Main entry point for the music-minion command."""
    # Create main parser
    parser = argparse.ArgumentParser(
        description="Music Minion - Contextual Music Curation",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    # Add global options
    parser.add_argument(
        '--dev',
        action='store_true',
        help='Enable hot-reload for development (requires watchdog)'
    )

    # Create subparsers for IPC commands
    subparsers = parser.add_subparsers(dest='subcommand', help='Available commands')

    # IPC commands for playback
    subparsers.add_parser('like', help='Like current track')
    subparsers.add_parser('love', help='Love current track')
    subparsers.add_parser('skip', help='Skip current track')

    # IPC commands for playlists
    add_parser = subparsers.add_parser('add', help='Add current track to playlist')
    add_parser.add_argument('playlist', nargs='+', help='Playlist name')

    # IPC composite actions (shortcuts)
    subparsers.add_parser('la', help='Like and add to current month playlist (e.g., Nov 25)')
    subparsers.add_parser('nq', help='Add to "Not Quite" playlist')
    subparsers.add_parser('ni', help='Add to "Not Interested" playlist and skip')

    # Utility commands (run directly, not via IPC)
    locate_parser = subparsers.add_parser(
        'locate-opus',
        help='Find opus files to replace existing MP3 track records'
    )
    locate_parser.add_argument(
        'folder',
        help='Folder containing opus files to match'
    )
    locate_parser.add_argument(
        '--apply',
        action='store_true',
        help='Actually update database (default: dry run)'
    )

    # Parse arguments
    args, unknown = parser.parse_known_args()

    # Handle IPC commands
    if args.subcommand:
        if args.subcommand == 'like':
            sys.exit(send_ipc_command('like', []))

        elif args.subcommand == 'love':
            sys.exit(send_ipc_command('love', []))

        elif args.subcommand == 'skip':
            sys.exit(send_ipc_command('skip', []))

        elif args.subcommand == 'add':
            playlist_name = ' '.join(args.playlist)
            sys.exit(send_ipc_command('add', [playlist_name]))

        elif args.subcommand == 'la':
            # Composite: like_and_add_dated
            sys.exit(send_ipc_command('composite', ['like_and_add_dated']))

        elif args.subcommand == 'nq':
            # Composite: add_not_quite
            sys.exit(send_ipc_command('composite', ['add_not_quite']))

        elif args.subcommand == 'ni':
            # Composite: add_not_interested_and_skip
            sys.exit(send_ipc_command('composite', ['add_not_interested_and_skip']))

        elif args.subcommand == 'locate-opus':
            # Run locate-opus utility directly
            sys.exit(run_locate_opus(args.folder, apply=args.apply))

    # No subcommand - start interactive mode
    if args.dev:
        os.environ['MUSIC_MINION_DEV_MODE'] = '1'

    # Delegate to main interactive mode
    from .main import interactive_mode
    interactive_mode()


if __name__ == "__main__":
    main()
