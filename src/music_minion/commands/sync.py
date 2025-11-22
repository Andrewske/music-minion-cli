"""
Sync command handlers for Music Minion CLI.

Context-aware sync that adapts to active library (local vs provider).
"""

from typing import List, Tuple

from music_minion.context import AppContext
from music_minion.core.output import log
from music_minion.domain import sync


def handle_sync_command(ctx: AppContext) -> Tuple[AppContext, bool]:
    """Context-aware sync - behavior depends on active library.

    Local library: Incremental import (detect changed files)
    Provider library: Sync likes + playlists from API

    Args:
        ctx: Application context

    Returns:
        (updated_context, should_continue)
    """
    from music_minion.core import database

    active_provider = database.get_active_provider()

    if active_provider == "local":
        # Incremental import for local files
        return _sync_local_incremental(ctx)
    elif active_provider == "all":
        log("❌ Cannot sync 'all' library. Switch to specific library:", level="error")
        log("  library active local", level="info")
        log("  library active soundcloud", level="info")
        return ctx, True
    else:
        # Provider sync (soundcloud, spotify, youtube)
        return _sync_provider(ctx, active_provider, full=False)


def handle_sync_full_command(ctx: AppContext) -> Tuple[AppContext, bool]:
    """Full sync bypassing cache - behavior depends on active library.

    Local library: Full filesystem scan + import all
    Provider library: Full sync from API (bypass incremental)

    Args:
        ctx: Application context

    Returns:
        (updated_context, should_continue)
    """
    from music_minion.core import database

    active_provider = database.get_active_provider()

    if active_provider == "local":
        # Full filesystem scan + import
        return _sync_local_full(ctx)
    elif active_provider == "all":
        log("❌ Cannot sync 'all' library. Switch to specific library:", level="error")
        log("  library active local", level="info")
        log("  library active soundcloud", level="info")
        return ctx, True
    else:
        # Provider full sync
        return _sync_provider(ctx, active_provider, full=True)


def _sync_local_incremental(ctx: AppContext) -> Tuple[AppContext, bool]:
    """Incremental import: detect changed files and import metadata.

    Args:
        ctx: Application context

    Returns:
        (updated_context, should_continue)
    """
    from loguru import logger

    logger.info("Starting incremental local sync...")

    # Detect files that changed since last sync
    changed_tracks = sync.detect_file_changes(ctx.config)

    if not changed_tracks:
        log("✓ All files in sync", level="info")
        return ctx, True

    log(
        f"Found {len(changed_tracks)} changed files, importing metadata...",
        level="info",
    )

    # Import metadata from changed files
    result = sync.sync_import(ctx.config, force_all=False, show_progress=True)

    log(f"✓ Imported {result.get('imported', 0)} tracks", level="info")

    # Reload tracks in context
    from music_minion import helpers

    ctx = helpers.reload_tracks(ctx)

    return ctx, True


def _sync_local_full(ctx: AppContext) -> Tuple[AppContext, bool]:
    """Full sync: scan filesystem for new files + import all.

    Args:
        ctx: Application context

    Returns:
        (updated_context, should_continue)
    """
    from loguru import logger
    from music_minion.core import database
    from music_minion.domain.library import scanner

    logger.info("Starting full local sync (filesystem scan)...")

    log("Scanning ~/Music for new files...", level="info")

    # Full filesystem scan with optimizations
    tracks = scanner.scan_music_library_optimized(ctx.config, show_progress=True)

    if not tracks:
        log("✓ No new files found", level="info")
        return ctx, True

    # Batch upsert into database
    log(f"Processing {len(tracks)} tracks...", level="info")
    added, updated = database.batch_upsert_tracks(tracks)

    log(f"✓ Added {added} new tracks, updated {updated} existing tracks", level="info")

    # Reload tracks in context
    from music_minion import helpers

    ctx = helpers.reload_tracks(ctx)

    return ctx, True


def _sync_provider(
    ctx: AppContext, provider_name: str, full: bool
) -> Tuple[AppContext, bool]:
    """Sync provider likes and playlists, respecting provider config."""
    from loguru import logger
    from music_minion.commands import library

    sync_type = "full" if full else "incremental"
    logger.info(f"Starting {sync_type} sync for provider: {provider_name}")

    sync_playlists = _should_sync_provider_playlists(ctx, provider_name)
    sync_scope = "likes + playlists" if sync_playlists else "likes only"
    log(f"Syncing {provider_name} ({sync_scope})...", level="info")

    ctx, _ = library.sync_library(ctx, provider_name, full=full)

    if sync_playlists:
        ctx, _ = library.sync_playlists(ctx, provider_name, full=full)

    return ctx, True


def _should_sync_provider_playlists(ctx: AppContext, provider_name: str) -> bool:
    """Return True when provider playlists should be synced automatically."""
    provider_config = getattr(ctx.config, provider_name, None)
    return (
        bool(getattr(provider_config, "sync_playlists", False))
        if provider_config
        else False
    )
