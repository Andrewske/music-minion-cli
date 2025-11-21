# Sync Command Refactor Plan

## Overview

Refactor the `sync` command to be library-aware, removing complexity and making it auto-run on startup. The key insight is that sync behavior should depend on the active library (local vs provider).

## Goals

1. **Simplicity**: Reduce from 4 subcommands to 2 main commands
2. **Efficiency**: Auto-sync on startup (must be <1 second)
3. **Context-aware**: Behavior changes based on active library
4. **Remove redundancy**: Eliminate commands that aren't needed

## Philosophy

### File as Source of Truth (Local Library)
- When changes made in Music Minion → update database AND file immediately
- When `sync` runs → import detects external changes (e.g., Serato edits on Windows)
- Export not needed if app always writes to files on change
- Import brings in new tracks and updates for files changed elsewhere

### Provider Sync
- Fetch likes + playlists from API (SoundCloud, Spotify, etc.)
- No file operations (providers are streaming URLs, not local files)
- Incremental by default (track last sync state)

## Current vs New Behavior

### Current Commands (4 subcommands)
- `sync export` - Write database tags → file metadata
- `sync import [--all]` - Import file metadata → database
- `sync status` - Show sync statistics
- `sync rescan [--full]` - Scan for new files + import

### New Commands (2 main commands)
- `sync` - Context-aware main sync
  - **Local**: Incremental import (detect changed files, import metadata)
  - **Provider**: Sync likes + playlists from API
- `sync full` - Full sync bypassing cache
  - **Local**: Full filesystem scan + import all
  - **Provider**: Full sync from API (bypass incremental tracking)

### Removed Commands
- `sync export` - Not needed (files always updated on change)
- `sync import` - Redundant (use `sync` instead)
- `sync status` - Rarely used (check logs for debugging)
- `sync rescan` - Confusing name (merged into `sync full`)

## Implementation Details

### 1. Command Routing Changes

**File**: `src/music_minion/router.py`

**Current routing** (lines 278-292):
```python
elif command == 'sync':
    if not args:
        print("Error: Sync command requires a subcommand...")
    elif args[0] == 'export':
        return sync.handle_sync_export_command(ctx)
    elif args[0] == 'import':
        return sync.handle_sync_import_command(ctx, args[1:])
    elif args[0] == 'status':
        return sync.handle_sync_status_command(ctx)
    elif args[0] == 'rescan':
        return sync.handle_sync_rescan_command(ctx, args[1:])
```

**New routing**:
```python
elif command == 'sync':
    if not args:
        # sync (no arguments) - context-aware sync
        return sync.handle_sync_command(ctx)
    elif args[0] == 'full':
        # sync full - full sync bypassing cache
        return sync.handle_sync_full_command(ctx)
    else:
        print(f"Unknown sync subcommand: '{args[0]}'. Available: full")
        return ctx, True
```

**Remove library sync routing**:
```python
# DELETE THIS BLOCK (deprecate library sync command)
elif args[0] == 'sync':
    return library.handle_library_sync_command(ctx, args[1:])
```

### 2. New Sync Command Handlers

**File**: `src/music_minion/commands/sync.py`

#### New Function: `handle_sync_command(ctx)`
```python
def handle_sync_command(ctx: AppContext) -> Tuple[AppContext, bool]:
    """Context-aware sync - behavior depends on active library.

    Local library: Incremental import (detect changed files)
    Provider library: Sync likes + playlists from API
    """
    active_provider = database.get_active_provider()

    if active_provider == 'local':
        # Incremental import for local files
        return _sync_local_incremental(ctx)
    elif active_provider == 'all':
        print("Error: Cannot sync 'all' library. Switch to specific library:")
        print("  library active local")
        print("  library active soundcloud")
        return ctx, True
    else:
        # Provider sync (soundcloud, spotify, youtube)
        return _sync_provider(ctx, active_provider, full=False)
```

#### New Function: `handle_sync_full_command(ctx)`
```python
def handle_sync_full_command(ctx: AppContext) -> Tuple[AppContext, bool]:
    """Full sync bypassing cache - behavior depends on active library.

    Local library: Full filesystem scan + import all
    Provider library: Full sync from API (bypass incremental)
    """
    active_provider = database.get_active_provider()

    if active_provider == 'local':
        # Full filesystem scan + import
        return _sync_local_full(ctx)
    elif active_provider == 'all':
        print("Error: Cannot sync 'all' library. Switch to specific library:")
        print("  library active local")
        print("  library active soundcloud")
        return ctx, True
    else:
        # Provider full sync
        return _sync_provider(ctx, active_provider, full=True)
```

#### Helper Function: `_sync_local_incremental(ctx)`
```python
def _sync_local_incremental(ctx: AppContext) -> Tuple[AppContext, bool]:
    """Incremental import: detect changed files and import metadata."""
    import logging
    logger = logging.getLogger(__name__)

    logger.info("Starting incremental local sync...")

    # Detect files that changed since last sync
    changed_tracks = detect_file_changes(ctx.config)

    if not changed_tracks:
        print("✓ All files in sync")
        return ctx, True

    print(f"Found {len(changed_tracks)} changed files, importing metadata...")

    # Import metadata from changed files
    result = sync_import(ctx.config, force_all=False, show_progress=True)

    print(f"✓ Imported {result.get('imported', 0)} tracks")

    # Reload tracks in context
    ctx = helpers.reload_tracks(ctx)

    return ctx, True
```

#### Helper Function: `_sync_local_full(ctx)`
```python
def _sync_local_full(ctx: AppContext) -> Tuple[AppContext, bool]:
    """Full sync: scan filesystem for new files + import all."""
    import logging
    logger = logging.getLogger(__name__)

    logger.info("Starting full local sync (filesystem scan)...")

    print("Scanning ~/Music for new files...")

    # Full filesystem scan with optimizations
    tracks = library.scan_music_library_optimized(
        ctx.config,
        show_progress=True
    )

    if not tracks:
        print("✓ No new files found")
        return ctx, True

    # Batch upsert into database
    print(f"Processing {len(tracks)} tracks...")
    added, updated = database.batch_upsert_tracks(tracks)

    print(f"✓ Added {added} new tracks, updated {updated} existing tracks")

    # Reload tracks in context
    ctx = helpers.reload_tracks(ctx)

    return ctx, True
```

#### Helper Function: `_sync_provider(ctx, provider_name, full)`
```python
def _sync_provider(ctx: AppContext, provider_name: str, full: bool) -> Tuple[AppContext, bool]:
    """Sync from provider API (soundcloud, spotify, youtube)."""
    import logging
    logger = logging.getLogger(__name__)

    sync_type = "full" if full else "incremental"
    logger.info(f"Starting {sync_type} sync for provider: {provider_name}")

    print(f"Syncing {provider_name} (likes + playlists)...")

    # Delegate to library.sync_library() function
    # (Keep the function, just remove command routing)
    return library.sync_library(
        ctx,
        provider_name,
        full=full,
        sync_types=['likes', 'playlists']  # Always both
    )
```

### 3. Database Helper Function

**File**: `src/music_minion/core/database.py`

Add new helper function (insert after `get_db_connection()`):

```python
def get_active_provider() -> str:
    """Get the currently active library provider.

    Returns:
        Provider name: 'local', 'soundcloud', 'spotify', 'youtube', or 'all'
    """
    with get_db_connection() as conn:
        cursor = conn.execute("SELECT provider FROM active_library WHERE id = 1")
        row = cursor.fetchone()
        return row["provider"] if row else "local"
```

### 4. Remove Deprecated Functions

**File**: `src/music_minion/commands/sync.py`

**DELETE** these functions:
- `handle_sync_export_command()`
- `handle_sync_import_command()`
- `handle_sync_status_command()`
- `handle_sync_rescan_command()`

**KEEP** these internal functions (used by new handlers):
- `detect_file_changes()` - Used by incremental import
- `sync_import()` - Used by both incremental and full sync
- Internal helpers in `domain/sync/engine.py`

**File**: `src/music_minion/commands/library.py`

**REMOVE** command routing for `library sync`:
- Delete `handle_library_sync_command()` function
- **KEEP** `sync_library()` internal function (called by `_sync_provider()`)

### 5. Hide 'all' Library in UI

**File**: `src/music_minion/commands/library.py`

In `handle_library_list_command()` (around line 143):

**Current**:
```python
cursor = conn.execute("SELECT DISTINCT source FROM tracks")
providers = [row["source"] for row in cursor.fetchall()]
providers.append('all')  # Always show 'all' option
```

**New**:
```python
cursor = conn.execute("SELECT DISTINCT source FROM tracks")
providers = [row["source"] for row in cursor.fetchall()]
# Don't show 'all' option (internal use only)
```

In `switch_active_library()` (around line 240):

**Keep validation** but don't show 'all' in help text:
```python
valid_providers = ['local', 'soundcloud', 'spotify', 'youtube']  # Remove 'all'
if provider_name not in valid_providers:
    print(f"Error: Unknown provider '{provider_name}'")
    print(f"Available providers: {', '.join(valid_providers)}")
    return False
```

## Performance Optimizations

### Current Bottleneck: Full Filesystem Scan (~30 seconds for 5000 files)

**Problem**: `scan_music_library()` is slow:
1. Uses `rglob("*")` to get ALL files, then filters
2. Single-threaded metadata extraction
3. Re-scans unchanged files every time

### Optimization 1: Smart Glob Patterns (2x faster)

**File**: `src/music_minion/domain/library/scanner.py`

**Current** (lines 39-48):
```python
if config.music.scan_recursive:
    files = directory.rglob("*")
else:
    files = directory.iterdir()

for local_path in files:
    if local_path.is_file() and is_supported_format(local_path, config.music.supported_formats):
        # Process file
```

**Optimized**:
```python
files = []
if config.music.scan_recursive:
    # Only glob music file extensions
    for ext in config.music.supported_formats:  # [".mp3", ".m4a", ".flac"]
        files.extend(directory.rglob(f"*{ext}"))
else:
    # Only iterate music files in immediate directory
    for ext in config.music.supported_formats:
        files.extend(directory.glob(f"*{ext}"))

for local_path in files:
    # Already filtered, no need to check format again
    if local_path.is_file():
        # Process file
```

**Impact**: 30s → 15s (skips non-music files during traversal)

### Optimization 2: Skip Unchanged Files (10-50x faster for re-scans)

**File**: `src/music_minion/domain/library/scanner.py`

Add new optimized function:

```python
def scan_music_library_optimized(
    config: Config, show_progress: bool = True
) -> List[Track]:
    """Optimized library scan that skips unchanged files.

    First scan: Normal speed (must extract all metadata)
    Subsequent scans: 10-50x faster (only process new/changed files)
    """
    import logging
    from music_minion.core import database

    logger = logging.getLogger(__name__)

    # Load known files from database with mtimes
    known_files = {}
    with database.get_db_connection() as conn:
        cursor = conn.execute("""
            SELECT local_path, file_mtime
            FROM tracks
            WHERE local_path IS NOT NULL
        """)
        for row in cursor.fetchall():
            known_files[row["local_path"]] = row["file_mtime"]

    logger.info(f"Database has {len(known_files)} known files")

    all_tracks = []
    skipped = 0
    processed = 0

    for library_path in config.music.library_paths:
        path = Path(library_path).expanduser()
        if not path.exists():
            print(f"Warning: Library path does not exist: {path}")
            continue

        # Get all music files using smart glob
        files = []
        for ext in config.music.supported_formats:
            if config.music.scan_recursive:
                files.extend(path.rglob(f"*{ext}"))
            else:
                files.extend(path.glob(f"*{ext}"))

        if show_progress:
            print(f"Found {len(files)} music files in {path}")

        # Process files
        for file_path in files:
            if not file_path.is_file():
                continue

            file_path_str = str(file_path)

            # Check if file is unchanged
            if file_path_str in known_files:
                current_mtime = os.stat(file_path_str).st_mtime
                stored_mtime = known_files[file_path_str]

                if stored_mtime and current_mtime <= stored_mtime:
                    # File unchanged, skip metadata extraction
                    skipped += 1
                    continue

            # New or changed file - extract metadata
            try:
                track = extract_track_metadata(file_path_str)
                all_tracks.append(track)
                processed += 1

                if show_progress and processed % 100 == 0:
                    print(f"  Processed {processed} files...")

            except Exception as e:
                logger.error(f"Error processing {file_path_str}: {e}")

    if show_progress:
        print(f"\nScan complete:")
        print(f"  Processed: {processed} new/changed files")
        print(f"  Skipped: {skipped} unchanged files")

    logger.info(f"Scan stats - processed: {processed}, skipped: {skipped}")

    return all_tracks
```

**Impact**:
- First scan: 30s → 15s (glob optimization)
- Subsequent `sync full`: 15s → 1-3s (mtime check skips most files)

### Optimization 3: Parallel Processing (DEFERRED to Phase 8)

**Rationale**: More complex, needs testing, marginal benefit after optimizations 1+2

Would use `concurrent.futures.ProcessPoolExecutor` for parallel metadata extraction.

## Auto-Sync on Startup

**File**: `src/music_minion/ui/blessed/app.py` (or `main.py`)

Add after app initialization, before main loop:

```python
def run_blessed_app(ctx: AppContext) -> AppContext:
    """Run the blessed terminal UI."""
    import logging
    logger = logging.getLogger(__name__)

    # Auto-sync on startup (fast incremental)
    logger.info("Running auto-sync on startup...")
    try:
        ctx, _ = sync.handle_sync_command(ctx)
    except Exception as e:
        logger.exception(f"Auto-sync failed: {e}")
        # Continue even if sync fails (non-critical)

    # Rest of app initialization...
```

**Requirements**:
- Must be fast (<1 second for incremental)
- Silent or minimal output (don't spam UI)
- Non-blocking (don't prevent app startup if sync fails)

## Testing Checklist

### Unit Tests
- [ ] `get_active_provider()` returns correct provider
- [ ] `handle_sync_command()` routes correctly based on active library
- [ ] `handle_sync_full_command()` routes correctly based on active library
- [ ] Smart glob patterns only return music files
- [ ] Mtime comparison skips unchanged files correctly

### Integration Tests
- [ ] Local incremental sync: only imports changed files
- [ ] Local full sync: discovers new files and imports all
- [ ] Provider sync: fetches likes + playlists from API
- [ ] Provider full sync: bypasses incremental cache
- [ ] Auto-sync on startup completes in <1 second
- [ ] Error when active library is 'all'
- [ ] 'all' library hidden in UI

### Performance Tests
- [ ] Incremental sync: <1 second for 5000 files with no changes
- [ ] Full sync (first time): ~15 seconds for 5000 files
- [ ] Full sync (re-scan): 1-3 seconds for 5000 files (most unchanged)
- [ ] Smart glob: verify 2x speedup over `rglob("*")`

### Edge Cases
- [ ] Empty library (no files)
- [ ] New library (never synced before)
- [ ] All files deleted
- [ ] Permission errors on files
- [ ] Corrupted audio files
- [ ] Provider API errors (rate limits, auth failures)
- [ ] Switching libraries and syncing

## Migration Guide

### For Users

**Old commands** → **New commands**:
- `sync import` → `sync`
- `sync import --all` → `sync full`
- `sync rescan` → `sync full`
- `sync export` → *(removed - not needed)*
- `sync status` → *(removed - check logs)*
- `library sync soundcloud` → `library active soundcloud` + `sync`
- `library sync soundcloud --full` → `library active soundcloud` + `sync full`

**New workflow**:
1. Switch to desired library: `library active soundcloud`
2. Sync: `sync` (or `sync full` for comprehensive)

**Auto-sync**: App automatically syncs on startup, manual sync rarely needed

### For Developers

**Removed functions**:
- `commands/sync.py::handle_sync_export_command()`
- `commands/sync.py::handle_sync_import_command()`
- `commands/sync.py::handle_sync_status_command()`
- `commands/sync.py::handle_sync_rescan_command()`
- `commands/library.py::handle_library_sync_command()`

**New functions**:
- `core/database.py::get_active_provider()`
- `commands/sync.py::handle_sync_command()`
- `commands/sync.py::handle_sync_full_command()`
- `domain/library/scanner.py::scan_music_library_optimized()`

**Internal functions (keep)**:
- `commands/library.py::sync_library()` - Still used by provider sync
- `domain/sync/engine.py::sync_import()` - Still used by local sync
- `domain/sync/engine.py::detect_file_changes()` - Still used by incremental

## Error Messages

### When active library is 'all':
```
Error: Cannot sync 'all' library. Switch to specific library:
  library active local
  library active soundcloud
```

### When provider not authenticated:
```
Error: Not authenticated with soundcloud. Run:
  library auth soundcloud
```

### When no changes detected:
```
✓ All files in sync
```

### When sync succeeds:
```
✓ Imported 15 tracks (3 new, 12 updated)
```

```
✓ Synced soundcloud: 42 likes, 8 playlists
```

## Implementation Order

1. **Add database helper** (`get_active_provider()`)
2. **Add optimized scanner** (`scan_music_library_optimized()`)
3. **Add new sync handlers** (`handle_sync_command()`, `handle_sync_full_command()`)
4. **Update router** (change sync routing, remove library sync routing)
5. **Remove deprecated functions** (export, import, status, rescan handlers)
6. **Hide 'all' library** (UI changes)
7. **Add auto-sync on startup**
8. **Update help text** (all command help references)
9. **Test thoroughly** (see testing checklist)

## Known Limitations

1. **Cannot sync multiple libraries at once**: Must switch active library first
2. **No granular provider sync**: Always syncs both likes + playlists (can't choose one)
3. **'all' library cannot be synced**: Must switch to specific library
4. **No sync status command**: Must check logs for debugging

These limitations are acceptable trade-offs for simplicity and auto-sync performance.

## Future Enhancements (Phase 8+)

1. **Background sync**: Run sync in background thread while app is running
2. **File watching**: Use `watchdog` library to detect file changes in real-time
3. **Parallel metadata extraction**: Use multiprocessing for 4-8x speedup
4. **Sync notifications**: Desktop notifications when sync completes
5. **Granular provider sync**: `sync likes` and `sync playlists` options
6. **Multi-library sync**: Sync all libraries with one command
7. **Conflict detection UI**: Visual diff when file and database disagree

---

**Document Version**: 1.0
**Last Updated**: 2025-11-20
**Author**: Claude Code Planning Session
**Related Docs**:
- `docs/playlist-system-plan.md` - Previous implementation phases
- `ai-learnings.md` - Patterns and best practices
