"""
Sync command handlers for Music Minion CLI.

Context-aware sync that adapts to active library (local vs provider).
"""

from music_minion.context import AppContext
from music_minion.core.output import log
from music_minion.domain import sync


def handle_sync_command(ctx: AppContext) -> tuple[AppContext, bool]:
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


def handle_sync_full_command(ctx: AppContext) -> tuple[AppContext, bool]:
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


def _sync_local_incremental(ctx: AppContext) -> tuple[AppContext, bool]:
    """Incremental sync: import from changed files only.

    Export removed from auto-sync because:
    1. DB is source of truth (no need to export on every load)
    2. update_track_metadata() already writes to files when user edits
    3. Prevents circular mtime updates (export changes mtimes → triggers import)

    Use manual 'sync full' command to force export when needed.

    Args:
        ctx: Application context

    Returns:
        (updated_context, should_continue)
    """
    from loguru import logger

    logger.info("Starting incremental local sync...")

    # Import metadata from changed files
    changed_tracks = sync.detect_file_changes(ctx.config)

    if changed_tracks:
        log(
            f"Found {len(changed_tracks)} changed files, importing metadata...",
            level="info",
        )
        result = sync.sync_import(ctx.config, force_all=False, show_progress=True)
        log(f"✓ Imported {result.get('added', 0)} tags from files", level="info")
    else:
        log("✓ No changed files to import from", level="info")

    # Reload tracks in context
    from music_minion import helpers

    ctx = helpers.reload_tracks(ctx)

    return ctx, True


def _sync_local_full(ctx: AppContext) -> tuple[AppContext, bool]:
    """Full sync: scan filesystem for new files + import all + export DB metadata.

    Args:
        ctx: Application context

    Returns:
        (updated_context, should_continue)
    """
    from loguru import logger
    from music_minion.core import database
    from music_minion.domain.library import scanner

    logger.info("Starting full local sync (filesystem scan)...")

    # Phase 1: Scan filesystem for new/changed files
    log("Scanning ~/Music for new files...", level="info")

    tracks = scanner.scan_music_library_optimized(ctx.config, show_progress=True)

    if tracks:
        # Batch upsert into database
        log(f"Processing {len(tracks)} tracks...", level="info")
        added, updated = database.batch_upsert_tracks(tracks)
        log(
            f"✓ Added {added} new tracks, updated {updated} existing tracks",
            level="info",
        )
    else:
        log("✓ No new files found", level="info")

    # Phase 2: Export DB metadata to files (ensures DB is source of truth)
    log("Exporting database metadata to files...", level="info")
    export_result = sync.sync_metadata_export(show_progress=True)
    log(
        f"✓ Exported metadata to {export_result.get('success', 0)} files",
        level="info",
    )

    # Reload tracks in context
    from music_minion import helpers

    ctx = helpers.reload_tracks(ctx)

    return ctx, True


def _sync_provider(
    ctx: AppContext, provider_name: str, full: bool
) -> tuple[AppContext, bool]:
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
