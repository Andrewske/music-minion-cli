"""
Music Minion CLI - Entry point with IPC support

This module serves as the CLI entry point, supporting both interactive mode
and IPC commands for hotkey integration.
"""

import argparse
import sys
import os
from music_minion import ipc


def run_sync_radio(force: bool = False, since: str | None = None) -> int:
    """Sync local music library and database to radio server.

    Args:
        force: If True, skip change detection and sync everything.
        since: If provided, sync tracks modified since this date (YYYY-MM-DD or 'today').

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    import subprocess
    from pathlib import Path

    SERVER = "root@46.62.221.136"
    LOCAL_MUSIC = Path.home() / "Music" / "radio-library"
    REMOTE_MUSIC = "/root/music/"
    PROJECT_ROOT = Path(__file__).parent.parent.parent
    IMPORT_SCRIPT = PROJECT_ROOT / "docker" / "radio" / "import_tracks.py"
    LAST_SYNC_FILE = PROJECT_ROOT / ".last_sync"

    print("=== Syncing to Radio Server ===")
    print()

    # Check if any files changed since last sync
    files_changed = True
    if not force and LAST_SYNC_FILE.exists():
        result = subprocess.run(
            ["find", str(LOCAL_MUSIC), "-newer", str(LAST_SYNC_FILE), "-type", "f"],
            capture_output=True,
            text=True,
            check=False
        )
        if result.returncode == 0 and not result.stdout.strip():
            files_changed = False
            print("[1/2] Syncing audio files... SKIPPED (no changes)")

    # Step 1: Sync audio files (only if changed)
    if files_changed:
        print("[1/2] Syncing audio files...")
        rsync_result = subprocess.run(
            ["rsync", "-avz", "--progress", "--delete", f"{LOCAL_MUSIC}/", f"{SERVER}:{REMOTE_MUSIC}"],
            check=False
        )
        if rsync_result.returncode != 0:
            print(f"Error: rsync failed with code {rsync_result.returncode}", file=sys.stderr)
            return 1

    # Step 2: Get DATABASE_URL from local .env
    print()
    print("[2/2] Importing to PostgreSQL...")
    env_file = PROJECT_ROOT / ".env"
    database_url = None
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("DATABASE_URL="):
                database_url = line.split("=", 1)[1]
                break

    if not database_url:
        print(f"Error: DATABASE_URL not found in {env_file}", file=sys.stderr)
        return 1

    # Step 3: Run import script
    import_cmd = ["uv", "run", "python", str(IMPORT_SCRIPT)]
    if force:
        import_cmd.append("--full")
    elif since:
        import_cmd.extend(["--since", since])
    import_result = subprocess.run(
        import_cmd,
        env={**os.environ, "DATABASE_URL": database_url},
        check=False
    )
    if import_result.returncode != 0:
        print(f"Error: import failed with code {import_result.returncode}", file=sys.stderr)
        return 1

    # Update last sync timestamp
    LAST_SYNC_FILE.touch()

    print()
    print("=== Sync complete ===")
    print("Stream: http://46.62.221.136:8080/stream")
    return 0


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
            print(
                f"{'Would update' if dry_run else 'Updated'}: {len(result.updated)} tracks"
            )
            for item in result.updated:
                tier = item.get("match_tier", "?")
                reason = item.get("match_reason", "unknown")
                score = item.get("match_score")
                score_str = f" ({score:.0%})" if score else ""
                print(f"  ✓ {item['opus_stem']}")
                print(
                    f"    → Track #{item['matched_track_id']}: {item.get('matched_title', 'Unknown')}"
                )
                print(f"    Match: Tier {tier} ({reason}){score_str}")
            print()

        if result.multiple_matches:
            print(
                f"Multiple matches (needs manual review): {len(result.multiple_matches)}"
            )
            for item in result.multiple_matches:
                tier = item.get("match_tier", "?")
                print(f"  ⚠ {item['opus_stem']}")
                print(f"    Opus title: {item.get('opus_title', 'Unknown')}")
                print(f"    Tier {tier} found {len(item.get('matches', []))} matches:")
                for match in item.get("matches", [])[:3]:
                    score = match.get("score")
                    score_str = f" ({score:.0%})" if score else ""
                    print(
                        f"      - #{match['id']}: {match.get('title', 'Unknown')}{score_str}"
                    )
            print()

        if result.no_match:
            print(f"No match found: {len(result.no_match)}")
            for item in result.no_match:
                print(f"  ✗ {item['opus_stem']}")
                print(f"    Title: {item.get('opus_title', 'Unknown')}")
                print(f"    Reason: {item.get('reason', 'unknown')}")
            print()

        # Summary
        total = (
            len(result.updated) + len(result.multiple_matches) + len(result.no_match)
        )
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


def send_web_command_remote_or_ipc(command: str, endpoint: str, data: dict) -> int:
    """
    Send web command to remote server if configured, otherwise use IPC.

    Args:
        command: IPC command name (fallback)
        endpoint: Remote API endpoint path
        data: JSON data for remote POST

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    from music_minion.core.config import load_config

    config = load_config()
    remote_server = config.web.remote_server

    if remote_server:
        try:
            import requests

            url = f"{remote_server}{endpoint}"
            response = requests.post(url, json=data, timeout=5)
            response.raise_for_status()
            print(f"Command sent to remote server")
            return 0
        except Exception as e:
            print(f"Failed to send command to remote server: {e}", file=sys.stderr)
            return 1
    else:
        # Fallback to local IPC
        return send_ipc_command(command, [])


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
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Add global options
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Enable hot-reload for development (requires watchdog)",
    )
    parser.add_argument(
        "--web",
        action="store_true",
        help="Enable web UI (starts backend + frontend dev servers)",
    )

    # Create subparsers for IPC commands
    subparsers = parser.add_subparsers(dest="subcommand", help="Available commands")

    # IPC commands for playback
    subparsers.add_parser("like", help="Like current track")
    subparsers.add_parser("love", help="Love current track")
    subparsers.add_parser("skip", help="Skip current track")

    # IPC commands for web interface control
    subparsers.add_parser("web-playpause", help="Toggle play/pause in web interface")
    subparsers.add_parser(
        "web-winner", help="Select current track A as winner in web interface"
    )
    subparsers.add_parser("web-archive", help="Archive current track in web interface")
    subparsers.add_parser("web-play1", help="Play first track in web interface")
    subparsers.add_parser("web-play2", help="Play second track in web interface")
    subparsers.add_parser(
        "web-seek-pos", help="Seek forward 10 seconds in web interface"
    )
    subparsers.add_parser(
        "web-seek-neg", help="Seek backward 10 seconds in web interface"
    )

    # IPC commands for playlists
    add_parser = subparsers.add_parser("add", help="Add current track to playlist")
    add_parser.add_argument("playlist", nargs="+", help="Playlist name")

    # IPC composite actions (shortcuts)
    subparsers.add_parser(
        "la", help="Like and add to current month playlist (e.g., Nov 25)"
    )
    subparsers.add_parser("nq", help='Add to "Not Quite" playlist')
    subparsers.add_parser("ni", help='Add to "Not Interested" playlist and skip')

    # Utility commands (run directly, not via IPC)
    locate_parser = subparsers.add_parser(
        "locate-opus", help="Find opus files to replace existing MP3 track records"
    )
    locate_parser.add_argument("folder", help="Folder containing opus files to match")
    locate_parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually update database (default: dry run)",
    )

    # Radio server sync
    sync_radio_parser = subparsers.add_parser(
        "sync-radio", help="Sync music files and database to radio server"
    )
    sync_radio_parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Force full sync (skip change detection)",
    )
    sync_radio_parser.add_argument(
        "--since", "-s",
        type=str,
        metavar="DATE",
        help="Sync tracks modified since DATE (YYYY-MM-DD or 'today')",
    )

    # Parse arguments
    args, unknown = parser.parse_known_args()

    # Handle IPC commands
    if args.subcommand:
        if args.subcommand == "like":
            sys.exit(send_ipc_command("like", []))

        elif args.subcommand == "love":
            sys.exit(send_ipc_command("love", []))

        elif args.subcommand == "skip":
            sys.exit(send_ipc_command("skip", []))

        elif args.subcommand == "web-playpause":
            sys.exit(send_ipc_command("web-playpause", []))

        elif args.subcommand == "web-winner":
            # Note: This needs session context to determine winner_id, track IDs, etc.
            # For now, just use IPC as remote comparison verdict needs full session state
            sys.exit(send_ipc_command("web-winner", []))

        elif args.subcommand == "web-archive":
            sys.exit(send_ipc_command("web-archive", []))

        elif args.subcommand == "web-play1":
            sys.exit(send_web_command_remote_or_ipc(
                "web-play1",
                "/api/comparisons/select-track",
                {"track_id": "track_a", "is_playing": True}
            ))

        elif args.subcommand == "web-play2":
            sys.exit(send_web_command_remote_or_ipc(
                "web-play2",
                "/api/comparisons/select-track",
                {"track_id": "track_b", "is_playing": True}
            ))

        elif args.subcommand == "web-seek-pos":
            sys.exit(send_ipc_command("web-seek-pos", []))

        elif args.subcommand == "web-seek-neg":
            sys.exit(send_ipc_command("web-seek-neg", []))

        elif args.subcommand == "add":
            playlist_name = " ".join(args.playlist)
            sys.exit(send_ipc_command("add", [playlist_name]))

        elif args.subcommand == "la":
            # Composite: like_and_add_dated
            sys.exit(send_ipc_command("composite", ["like_and_add_dated"]))

        elif args.subcommand == "nq":
            # Composite: add_not_quite
            sys.exit(send_ipc_command("composite", ["add_not_quite"]))

        elif args.subcommand == "ni":
            # Composite: add_not_interested_and_skip
            sys.exit(send_ipc_command("composite", ["add_not_interested_and_skip"]))

        elif args.subcommand == "locate-opus":
            # Run locate-opus utility directly
            sys.exit(run_locate_opus(args.folder, apply=args.apply))

        elif args.subcommand == "sync-radio":
            # Sync to radio server
            sys.exit(run_sync_radio(force=args.force, since=args.since))

    # No subcommand - start interactive mode
    if args.dev:
        os.environ["MUSIC_MINION_DEV_MODE"] = "1"
    if args.web:
        os.environ["MUSIC_MINION_WEB_MODE"] = "1"

    # Delegate to main interactive mode
    from .main import interactive_mode

    interactive_mode()


if __name__ == "__main__":
    main()
