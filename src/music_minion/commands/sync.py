"""
Sync command handlers for Music Minion CLI.

Context-aware sync that adapts to active library (local vs provider).
"""

from music_minion.context import AppContext
from music_minion.core.output import log
from music_minion.domain import sync


def handle_sync_command(ctx: AppContext, args: list[str] = None) -> tuple[AppContext, bool]:
    """Full smart sync: find new files + bidirectional metadata sync.

    For local library: Scan for new files, detect changes in both directions,
    merge non-conflicts, report conflicts with field-level diffs.
    For provider libraries: Delegate to existing provider sync (unchanged).

    Args:
        ctx: Application context
        args: Optional args like --ours, --theirs, --dry-run

    Usage:
        sync              # Full sync: find new + import/export changes
        sync --dry-run    # Preview what would happen (no changes)
        sync --ours       # Resolve conflicts: DB wins
        sync --theirs     # Resolve conflicts: file wins
    """
    from pathlib import Path
    from music_minion.core import database
    from music_minion.domain.sync.engine import (
        analyze_sync_status, execute_sync_actions, ConflictStrategy,
        SyncAction, sync_lock
    )
    from music_minion.domain.library import scanner

    active_provider = database.get_active_provider()

    # Provider libraries use existing sync (unchanged)
    if active_provider != "local":
        if active_provider == "all":
            log("Cannot sync 'all' library. Switch to specific library.", level="error")
            return ctx, True
        return _sync_provider(ctx, active_provider, full=False)

    # Parse args
    args = args or []
    dry_run = "--dry-run" in args
    strategy = ConflictStrategy.OURS  # default: DB wins
    if "--theirs" in args:
        strategy = ConflictStrategy.THEIRS

    with sync_lock(ctx.config):
        # Phase 1: Scan for new files
        log("Scanning for new files...", level="info")
        tracks = scanner.scan_music_library_optimized(ctx.config, show_progress=False)
        if tracks:
            added, updated = database.batch_upsert_tracks(tracks)
            if added > 0:
                log(f"Found {added} new tracks", level="info")
                from music_minion.domain.playlists.filters import (
                    refresh_all_smart_playlists,
                )
                refresh_all_smart_playlists()

        # Phase 2: Analyze sync status
        log("Analyzing sync status...", level="info")
        results, stats = analyze_sync_status(ctx.config)

        # Filter to only actionable results
        actionable = [r for r in results if r.action != SyncAction.SKIP]

        if not actionable:
            log("Everything is in sync.", level="info")
            return ctx, True

        # Show summary with field-level diff for conflicts
        imports = [r for r in actionable if r.action == SyncAction.IMPORT]
        exports = [r for r in actionable if r.action == SyncAction.EXPORT]
        conflicts = [r for r in actionable if r.action == SyncAction.CONFLICT]

        if imports:
            log(f"  {len(imports)} to import (file → DB)", level="info")
        if exports:
            log(f"  {len(exports)} to export (DB → file)", level="info")
        if conflicts:
            log(f"  {len(conflicts)} conflicts:", level="warning")
            for r in conflicts[:5]:
                log(f"    {Path(r.local_path).name}", level="warning")
                # Field-level diff for conflicts
                if r.conflict_fields and r.file_metadata and r.db_metadata:
                    for field in r.conflict_fields:
                        file_val = r.file_metadata.get(field, '?')
                        db_val = r.db_metadata.get(field, '?')
                        log(f"      {field}: {file_val} (file) ≠ {db_val} (db)", level="warning")
            if len(conflicts) > 5:
                log(f"    ... and {len(conflicts) - 5} more", level="warning")

        if dry_run:
            log("\nDry run - no changes made. Remove --dry-run to apply.", level="info")
            return ctx, True

        # Phase 3: Execute sync actions
        exec_stats = execute_sync_actions(ctx.config, actionable, strategy=strategy)

        log(f"Sync complete: {exec_stats.get('imported', 0)} imported, "
            f"{exec_stats.get('exported', 0)} exported, "
            f"{exec_stats.get('conflicts_resolved', 0)} conflicts resolved", level="info")

    # Reload tracks in context
    from music_minion import helpers
    ctx = helpers.reload_tracks(ctx)

    return ctx, True


def handle_sync_pull_command(ctx: AppContext, args: list[str]) -> tuple[AppContext, bool]:
    """Force import: file metadata → database. Trust files.

    Usage:
        sync pull           # Import changed files only
        sync pull --all     # Full filesystem scan + import all metadata
        sync pull --dry-run # Preview what would be imported
    """
    from music_minion.core import database
    from music_minion.domain import sync
    from music_minion.domain.library import scanner
    from music_minion.domain.sync.engine import sync_lock

    active_provider = database.get_active_provider()
    if active_provider != "local":
        log("sync pull is only for local library. Use 'sync' for providers.", level="error")
        return ctx, True

    force_all = "--all" in args
    dry_run = "--dry-run" in args

    with sync_lock(ctx.config):
        if force_all:
            # Full filesystem scan
            log("Scanning ~/Music for new files...", level="info")
            tracks = scanner.scan_music_library_optimized(ctx.config, show_progress=True)
            if tracks and not dry_run:
                added, updated = database.batch_upsert_tracks(tracks)
                log(f"Found {added} new tracks, updated {updated} existing", level="info")
                if added > 0:
                    from music_minion.domain.playlists.filters import (
                        refresh_all_smart_playlists,
                    )
                    refresh_all_smart_playlists()
            elif tracks:
                log(f"Would add {len(tracks)} tracks", level="info")

            log("Importing metadata from ALL files...", level="info")
        else:
            log("Importing metadata from changed files...", level="info")

        if dry_run:
            # Just show what would happen
            stats = sync.sync_pull(ctx.config, force_all=force_all, dry_run=True)
            log(f"Would import: {stats.get('to_import', 0)} tracks", level="info")
            log("Dry run - no changes made.", level="info")
            return ctx, True

        stats = sync.sync_pull(ctx.config, force_all=force_all)

        log(f"Import complete: {stats.get('imported', 0)} tracks updated, "
            f"{stats.get('failed', 0)} failed", level="info")

    # Reload tracks
    from music_minion import helpers
    ctx = helpers.reload_tracks(ctx)

    return ctx, True


def handle_sync_push_command(ctx: AppContext, args: list[str]) -> tuple[AppContext, bool]:
    """Force export: database metadata → files. Trust database.

    Usage:
        sync push           # Export only changed records
        sync push --all     # Export all records (force full)
        sync push --dry-run # Preview what would be exported
    """
    from music_minion.core import database
    from music_minion.domain import sync
    from music_minion.domain.sync.engine import sync_lock

    active_provider = database.get_active_provider()
    if active_provider != "local":
        log("sync push is only for local library.", level="error")
        return ctx, True

    force_all = "--all" in args
    dry_run = "--dry-run" in args

    with sync_lock(ctx.config):
        if force_all:
            log("Exporting metadata to ALL files...", level="info")
        else:
            log("Exporting metadata to changed files...", level="info")

        if dry_run:
            stats = sync.sync_push(ctx.config, force_all=force_all, dry_run=True)
            log(f"Would export: {stats.get('to_export', 0)} files", level="info")
            log("Dry run - no changes made.", level="info")
            return ctx, True

        stats = sync.sync_push(ctx.config, force_all=force_all)

        log(f"Export complete: {stats.get('exported', 0)} files written, "
            f"{stats.get('failed', 0)} failed", level="info")

    return ctx, True


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

    # Cleanup: Detect and handle missing/moved files
    cleanup_result = sync.detect_missing_and_moved_files(ctx.config)
    if cleanup_result['relocated'] > 0:
        log(f"✓ Relocated {cleanup_result['relocated']} moved files", level="info")
    if cleanup_result['deleted'] > 0:
        log(f"✓ Removed {cleanup_result['deleted']} orphaned tracks", level="info")

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
        if added > 0:
            from music_minion.domain.playlists.filters import (
                refresh_all_smart_playlists,
            )
            refresh_all_smart_playlists()
    else:
        log("✓ No new files found", level="info")

    # Phase 2: Export DB metadata to files (ensures DB is source of truth)
    log("Exporting database metadata to files...", level="info")
    export_result = sync.sync_metadata_export(show_progress=True)
    log(
        f"✓ Exported metadata to {export_result.get('success', 0)} files",
        level="info",
    )

    # Phase 3: Export ELO ratings to files
    log("Exporting ELO ratings to files...", level="info")
    elo_result = sync.sync_elo_export(show_progress=True)
    log(f"✓ Exported ELO to {elo_result.get('success', 0)} files", level="info")

    # Phase 4: Cleanup: Detect and handle missing/moved files
    cleanup_result = sync.detect_missing_and_moved_files(ctx.config)
    if cleanup_result['relocated'] > 0:
        log(f"✓ Relocated {cleanup_result['relocated']} moved files", level="info")
    if cleanup_result['deleted'] > 0:
        log(f"✓ Removed {cleanup_result['deleted']} orphaned tracks", level="info")

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
