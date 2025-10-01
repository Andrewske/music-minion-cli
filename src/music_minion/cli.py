"""
Music Minion CLI - Minimal entry point

This module serves as the CLI entry point, delegating to the main application logic.
"""

import argparse
import os


def main() -> None:
    """Main entry point for the music-minion command."""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Music Minion - Contextual Music Curation")
    parser.add_argument(
        '--dev',
        action='store_true',
        help='Enable hot-reload for development (requires watchdog)'
    )
    args = parser.parse_args()

    # Set environment variable for dev mode (accessed by main.py)
    if args.dev:
        os.environ['MUSIC_MINION_DEV_MODE'] = '1'

    # Delegate to main interactive mode
    from .main import interactive_mode
    interactive_mode()


if __name__ == "__main__":
    main()
