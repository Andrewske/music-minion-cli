---
task: 03-command-handlers
status: done
depends: [02-sync-engine-core]
files:
  - path: src/music_minion/commands/sync.py
    action: modify
---

# Sync Command Handlers

## Context
Implement the new command handlers for `sync`, `sync pull`, and `sync push`. These wrap the core engine functions and handle context-aware routing (local vs provider libraries). The `--dry-run` flag replaces the separate `sync status` command.

## Files to Modify/Create
- src/music_minion/commands/sync.py (modify)

## Implementation Details

### Modify `handle_sync_command`

Update existing function to support bidirectional sync with conflict resolution args:

```python
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
```

### Add `handle_sync_pull_command`

```python
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
```

### Add `handle_sync_push_command`

```python
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
```

## Verification
1. Run `sync --dry-run` - should show pending changes with field-level diff for conflicts
2. Run `sync` - should find new files + handle bidirectional sync
3. Run `sync pull --dry-run` - should show what would be imported
4. Run `sync pull --all` - should scan filesystem + import all files
5. Run `sync push --dry-run` - should show what would be exported
6. Run `sync push --all` - should export all files
7. Run `sync --ours` - should resolve conflicts with DB winning
8. Run `sync --theirs` - should resolve conflicts with file winning
9. Test concurrent sync - second sync should fail with "already running"
10. Test with provider active (e.g., soundcloud) - `sync pull` should error, `sync` should work as before
