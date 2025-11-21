"""
Music Minion CLI - Entry point with IPC support

This module serves as the CLI entry point, supporting both interactive mode
and IPC commands for hotkey integration.
"""

import argparse
import sys
import os
from music_minion import ipc, notifications


def send_ipc_command(command: str, args: list, notify: bool = True) -> int:
    """
    Send a command to running Music Minion instance via IPC.

    Args:
        command: Command name
        args: Command arguments
        notify: Whether to show desktop notification

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    success, message = ipc.send_command(command, args)

    # Show notification if requested (default ON)
    if notify:
        if success:
            notifications.notify_success(message)
        else:
            notifications.notify_error(message)

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
    parser.add_argument(
        '--no-notify',
        action='store_true',
        help='Disable desktop notifications for IPC commands'
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

    # Parse arguments
    args, unknown = parser.parse_known_args()

    # Handle IPC commands
    if args.subcommand:
        notify = not args.no_notify

        if args.subcommand == 'like':
            sys.exit(send_ipc_command('like', [], notify))

        elif args.subcommand == 'love':
            sys.exit(send_ipc_command('love', [], notify))

        elif args.subcommand == 'skip':
            sys.exit(send_ipc_command('skip', [], notify))

        elif args.subcommand == 'add':
            playlist_name = ' '.join(args.playlist)
            sys.exit(send_ipc_command('add', [playlist_name], notify))

        elif args.subcommand == 'la':
            # Composite: like_and_add_dated
            sys.exit(send_ipc_command('composite', ['like_and_add_dated'], notify))

        elif args.subcommand == 'nq':
            # Composite: add_not_quite
            sys.exit(send_ipc_command('composite', ['add_not_quite'], notify))

        elif args.subcommand == 'ni':
            # Composite: add_not_interested_and_skip
            sys.exit(send_ipc_command('composite', ['add_not_interested_and_skip'], notify))

    # No subcommand - start interactive mode
    if args.dev:
        os.environ['MUSIC_MINION_DEV_MODE'] = '1'

    # Delegate to main interactive mode
    from .main import interactive_mode
    interactive_mode()


if __name__ == "__main__":
    main()
