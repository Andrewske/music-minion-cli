"""
Sync command handlers for Music Minion CLI.

Handles: sync export, sync import, sync status, sync rescan
"""

from typing import List, Tuple

from ..context import AppContext
from ..domain import sync


def handle_sync_export_command(ctx: AppContext) -> Tuple[AppContext, bool]:
    """Handle sync export command - write all database tags to file metadata.

    Args:
        ctx: Application context

    Returns:
        (updated_context, should_continue)
    """
    print("Starting metadata export...")
    stats = sync.sync_export(ctx.config, show_progress=True)

    return ctx, True


def handle_sync_import_command(ctx: AppContext, args: List[str]) -> Tuple[AppContext, bool]:
    """Handle sync import command - read tags from file metadata to database.

    Args:
        ctx: Application context
        args: Command arguments

    Returns:
        (updated_context, should_continue)
    """
    force_all = '--all' in args or '-a' in args

    if force_all:
        print("Forcing full import from all files...")
    else:
        print("Importing from changed files...")

    stats = sync.sync_import(ctx.config, force_all=force_all, show_progress=True)

    return ctx, True


def handle_sync_status_command(ctx: AppContext) -> Tuple[AppContext, bool]:
    """Handle sync status command - show sync statistics.

    Args:
        ctx: Application context

    Returns:
        (updated_context, should_continue)
    """
    status = sync.get_sync_status(ctx.config)

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

    return ctx, True


def handle_sync_rescan_command(ctx: AppContext, args: List[str]) -> Tuple[AppContext, bool]:
    """Handle sync rescan command - rescan library for changes.

    Args:
        ctx: Application context
        args: Command arguments

    Returns:
        (updated_context, should_continue)
    """
    full_rescan = '--full' in args or '-f' in args

    stats = sync.rescan_library(ctx.config, full_rescan=full_rescan, show_progress=True)

    return ctx, True
