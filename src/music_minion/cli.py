"""
Music Minion CLI - Minimal entry point

This module serves as the CLI entry point, delegating to the main application logic.
"""


def main() -> None:
    """Main entry point for the music-minion command."""
    from .main import interactive_mode

    interactive_mode()


if __name__ == "__main__":
    main()
