# CLAUDE.md

Music Minion CLI: Contextual music curation with multi-source support (local, SoundCloud, Spotify)

## Project Context

**Personal Project - Single User**:
- This is a personal tool for one user (me)
- May share with others later, but not currently
- **No production-ready requirements**: Breaking changes are fine
- **No backwards compatibility needed**: Delete old code, refactor aggressively
- **No phased rollouts**: Ship changes immediately
- **Fast iteration over stability**: Move quickly, fix issues as they arise

**What This Means**:
- ✅ Aggressive refactoring without deprecation warnings
- ✅ Breaking database schema changes (can manually migrate)
- ✅ Remove unused code immediately (no "just in case")
- ✅ Experimental features can go straight to main
- ✅ Skip migration paths - direct upgrades only
- ❌ No feature flags for gradual rollout
- ❌ No backwards compatibility shims
- ❌ No multi-version support

## Architecture

**Functional over Classes (CRITICAL)**:
- ALWAYS question if a class is necessary - prefer functions with explicit state passing
- Only use classes for: NamedTuple, dataclass, or framework requirements with explicit justification
- Pass state explicitly via `AppContext` dataclass, never global variables
- Pure functions: take context, return new context - no mutations
- Command handlers: `(AppContext, str, list) -> (AppContext, bool)`

**blessed UI Three-Tier Rendering**:
- Full redraw: Track change, terminal resize, initial render
- Input redraw: Typing, command palette filtering
- Partial redraw: Clock/progress bar only (flicker elimination)
- Immutable state: All updates via `dataclasses.replace()`, never mutation
- Pure render functions: `(terminal, state, position) -> height_used`
- **Always use `write_at()` for positioned output** (clears line by default, prevents text overlap)

**Multi-Source Provider Architecture**:
- Provider protocol: Pure functions (`authenticate()`, `sync_library()`, `get_stream_url()`)
- Immutable `ProviderState` dataclass with builder methods
- No global variables or class instance state
- Background syncing: Thread-safe state updates via global sync state
- Track deduplication: TF-IDF cosine similarity matching

**UI Component Organization**:
- Keyboard handlers: `ui/blessed/events/keys/` (modular by mode: normal, wizard, comparison, playlist_builder, etc.)
- Components: `ui/blessed/components/` (pure render functions)
- Helpers: `ui/blessed/helpers/` (scrolling, terminal utilities, `write_at()`)
- State selectors: `ui/blessed/state_selectors.py` (memoized state derivations)
- Internal commands: `ui/blessed/events/commands/executor.py` (async command handlers)

**UI Mode System**:
- Mode detection via `detect_mode()` in `events/keyboard.py`
- Priority order: comparison > wizard > builder > track_viewer > analytics > editor > normal
- Each mode has: state fields in `UIState`, key handler, render component
- State mutations via `dataclasses.replace()` (immutable updates)

## Code Requirements

**Logging (CRITICAL)**:
```python
# Background operations - use loguru directly
from loguru import logger
logger.info("message")
logger.exception("error")  # In except blocks for stack traces

# User-facing - use unified log() helper (dual output: file + UI)
from music_minion.core.output import log
log("✅ Success", level="info")

# Background threads - suppress stdout
threading.current_thread().silent_logging = True
```

**NEVER use print()** - logs lost on restart, no rotation, breaks blessed UI

**Always use `uv run`** for Python script execution

**Type Safety**:
- Type hints required for parameters and returns
- No circular imports

**Imports**:
- Absolute imports preferred (`from music_minion.core import database`)
- Exception: `__init__.py` files and sibling modules within same package

**Functions**:
- ≤20 lines, ≤3 nesting levels
- Single responsibility

## Critical Patterns

**Data Loss Prevention**:
- Track data ownership: `source='user'|'ai'|'file'|'soundcloud'|'spotify'`
- NEVER remove data without checking ownership
- Only remove data you own (e.g., only remove `source='file'` tags during import)

**Atomic File Operations (Mutagen)**:
```python
temp_path = file_path + '.tmp'
try:
    shutil.copy2(file_path, temp_path)
    audio = MutagenFile(temp_path)
    # ... modify ...
    audio.save()
    os.replace(temp_path, file_path)  # Atomic
except Exception:
    if os.path.exists(temp_path): os.remove(temp_path)
    raise
```

**Database**:
- Batch updates: `executemany()` (30% faster)
- Single transaction: Commit once after all updates
- Always: `with get_db_connection() as conn:`

**Error Handling**:
- Use `logger.exception()` in except blocks (auto stack traces)
- NEVER bare except - catch specific exceptions
- Include context: file, provider, playlist name
- Background threads: Must wrap in try/except (exceptions don't propagate)

**Progress Reporting**:
- Scale with data: `max(1, total // 100)` for 1% intervals
- Use callbacks for thread-safe UI updates

**Change Detection**:
- mtime: Float timestamps for sub-second precision
- Get mtime AFTER write to capture own changes

## Development

**Commands**:
- Primary: `music-minion`
- Dev mode: `music-minion --dev` (hot-reload)
- IPC: `music-minion-cli play|skip|love|...`

**Key Dependencies**:
- mutagen (MP3/M4A metadata)
- blessed (terminal UI)
- loguru (centralized logging)
- spotipy (Spotify API)

**Database**: SQLite schema v22 in `core/database.py`
- Migrations: Idempotent with try/except for duplicate columns
- Key tables: `tracks`, `playlists`, `playlist_tracks`, `playlist_builder_state`

## Documentation References

- `ai-learnings.md` - Patterns, best practices, gotchas
- `docs/playlist-system-plan.md` - Implementation history
- `docs/incomplete-items.md` - Future roadmap

## Recent Features

**Playlist Builder** (v22):
- Bulk track selection for playlist building
- Entry: Press `b` from track viewer on manual playlist
- Sort by: title, artist, year, album, genre, bpm
- Filter with text/numeric operators (contains, equals, >, <, etc.)
- State persistence: scroll position, sort, filters saved per playlist
- Files: `components/playlist_builder.py`, `events/keys/playlist_builder.py`

**ELO Rating System**:
- Track comparison mode for rating tracks
- Rating history viewer
- Comparison history viewer

---

**Last Updated**: 2025-11-25
