"""
Sync command handlers for Music Minion CLI.

Handles: sync export, sync import, sync status, sync rescan
"""

from typing import List

from .. import sync


def get_config():
    """Get current config from main module."""
    from .. import main
    return main.current_config


def handle_sync_export_command() -> bool:
    """Handle sync export command - write all database tags to file metadata."""
    current_config = get_config()

    print("Starting metadata export...")
    stats = sync.sync_export(current_config, show_progress=True)

    return True


def handle_sync_import_command(args: List[str]) -> bool:
    """Handle sync import command - read tags from file metadata to database."""
    current_config = get_config()

    force_all = '--all' in args or '-a' in args

    if force_all:
        print("Forcing full import from all files...")
    else:
        print("Importing from changed files...")

    stats = sync.sync_import(current_config, force_all=force_all, show_progress=True)

    return True


def handle_sync_status_command() -> bool:
    """Handle sync status command - show sync statistics."""
    current_config = get_config()

    status = sync.get_sync_status(current_config)

    print("\n📊 Sync Status")
    print("=" * 50)
    print(f"Total tracks: {status['total_tracks']}")
    print(f"Changed files needing import: {status['changed_files']}")
    print(f"Never synced: {status['never_synced']}")

    if status['last_sync']:
        print(f"Last sync: {status['last_sync']}")
    else:
        print("Last sync: Never")

    print(f"Sync enabled: {'✅ Yes' if status['sync_enabled'] else '❌ No'}")
    print()

    if status['changed_files'] > 0:
        print(f"💡 Run 'sync import' to import {status['changed_files']} changed file(s)")

    return True


def handle_sync_rescan_command(args: List[str]) -> bool:
    """Handle sync rescan command - rescan library for changes."""
    current_config = get_config()

    full_rescan = '--full' in args or '-f' in args

    stats = sync.rescan_library(current_config, full_rescan=full_rescan, show_progress=True)

    return True
