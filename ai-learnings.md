# AI Learnings - Music Minion CLI

This file tracks learnings about the project structure, patterns, and best practices to help with future development.

## Project Structure

### Core Modules Location
- **Database**: `src/music_minion/database.py` - All SQLite operations, schema migrations
- **Sync**: `src/music_minion/sync.py` - Bidirectional metadata sync (database ↔ files)
- **Playlist**: `src/music_minion/playlist.py` - Playlist CRUD operations
- **Playlist Filters**: `src/music_minion/playlist_filters.py` - Smart playlist filter logic
- **Main**: `src/music_minion/main.py` - CLI entry point, command handlers
- **Config**: `src/music_minion/config.py` - Configuration management (TOML)
- **UI blessed**: `src/music_minion/ui/blessed/` - blessed-based interactive UI

### Test Files
- Adhoc test scripts in project root (e.g., `test_sync_fixes.py`)
- Delete after testing or keep for regression

### Documentation
- **Main Plan**: `docs/playlist-system-plan.md` - Implementation plan with phases, learnings
- **Project Guide**: `CLAUDE.md` - Development guidelines for AI assistants
- **Global Prefs**: `~/.claude/CLAUDE.md` - User's global development preferences

## blessed UI Implementation (Complete)

### Architecture Overview
**Decision**: Migrated from Textual to blessed for full control and functional programming style

**Benefits Achieved**:
- ✅ Fully functional approach (no classes except data containers)
- ✅ Direct terminal control without framework overhead
- ✅ Proper fixed header/scrollable/fixed footer layout
- ✅ Lightweight and fast
- ✅ Full keyboard handling with explicit state passing

### Module Structure
```
src/music_minion/ui/blessed/
├── __init__.py           # Module exports
├── dashboard.py          # Main blessed dashboard
└── command_palette.py    # Command palette widget
```

### Key Patterns

#### 1. Functional State Management
**Pattern**: Explicit state passing with immutable dataclasses
```python
@dataclass(frozen=True)
class DashboardState:
    player_state: PlayerState
    track_metadata: Optional[TrackMetadata]
    messages: List[str]

# Pure functions that return new state
def update_state(state: DashboardState, ...) -> DashboardState:
    return dataclasses.replace(state, ...)
```

**Benefits**:
- Easier testing (pure functions)
- Clearer data flow
- No hidden mutations
- Follows functional programming principles

#### 2. Direct Terminal Control
**Pattern**: Use blessed's terminal capabilities directly
```python
with term.hidden_cursor(), term.fullscreen():
    # Draw dashboard
    print(term.move(0, 0) + header)
    print(term.move(term.height - 3, 0) + footer)
```

**Benefits**:
- Full control over rendering
- No framework abstraction layer
- Explicit positioning
- Lightweight

#### 3. Event Loop with Explicit State
**Pattern**: Main loop with explicit state updates
```python
state = DashboardState(...)
while running:
    # Poll for input
    key = term.inkey(timeout=0.5)

    # Update state based on input
    if key:
        state = handle_key(state, key)

    # Re-render
    render(term, state)
```

**Benefits**:
- Clear control flow
- Easy to debug
- No hidden state changes
- Explicit update cycle

#### 4. Partial Rendering for Smooth Updates (Anti-Flashing)
**Problem**: Full screen redraws every second cause visible flashing when only time-sensitive elements (clock, progress bar) change.

**Solution**: Three-tier update strategy
```python
# State hash excludes volatile data (like position)
state_hash = hash((
    track_file,          # Include
    is_playing,          # Include
    duration,            # Include
    current_position,    # EXCLUDE - changes every second
))

# Track position separately
last_position = None

if needs_full_redraw:
    # Full redraw: clear screen, render everything
    print(term.clear)
    render_dashboard(...)
    last_position = int(current_position)

elif input_changed:
    # Input-only update: clear and redraw input area
    render_input(...)

else:
    # Partial update: only time-sensitive elements
    position = int(current_position)
    if position != last_position:
        render_dashboard_partial(...)  # Updates clock, progress bar only
        last_position = position
```

**Key Implementation**: `render_dashboard_partial()`
```python
def render_dashboard_partial(term, player_state, ui_state, y_start):
    # Update clock (line 0)
    print(term.move_xy(0, y_start) + term.clear_eol + header, end='')

    # Update progress bar (line 7)
    progress_y = y_start + 7
    print(term.move_xy(0, progress_y) + term.clear_eol + progress_bar, end='')

    # No term.clear() - no flashing!
```

**Benefits**:
- ✅ Eliminates flashing - static content never redraws
- ✅ Smooth playback progress updates
- ✅ Professional UI appearance
- ✅ Minimal performance overhead
- ✅ Clock and progress bar update independently

**Files**:
- `src/music_minion/ui/blessed/app.py` - Main loop with three-tier logic
- `src/music_minion/ui/blessed/components/dashboard.py` - Full and partial render functions

## Code Patterns & Conventions

### Database Operations

**Pattern**: Always use context managers for database connections
```python
with get_db_connection() as conn:
    cursor = conn.execute("SELECT ...")
    conn.commit()
```

**Pattern**: Batch updates for performance
```python
updates = []
for item in items:
    updates.append((value, id))
conn.executemany("UPDATE tracks SET col = ? WHERE id = ?", updates)
conn.commit()
```

**Migration Pattern**: Version-based, idempotent migrations in `database.py`
```python
if current_version < N:
    # Migration from v(N-1) to vN
    try:
        conn.execute("ALTER TABLE ...")
    except sqlite3.OperationalError as e:
        if "duplicate column" not in str(e).lower():
            raise
    conn.commit()
```

### File Operations

**Pattern**: Always use atomic writes for user data (mutagen requires file to exist)
```python
import shutil

temp_path = file_path + '.tmp'
try:
    shutil.copy2(file_path, temp_path)  # Copy original to temp
    audio = MutagenFile(temp_path)      # Load temp file
    # ... modify audio tags ...
    audio.save()                         # Save in place (no filename)
    os.replace(temp_path, file_path)    # Atomic replace
except Exception:
    if os.path.exists(temp_path):
        os.remove(temp_path)
    raise
```

**Pattern**: Check file existence before operations
```python
if not os.path.exists(file_path):
    return False  # or handle appropriately
```

**Pattern**: Validate file format explicitly
```python
audio = MutagenFile(file_path, easy=False)
if not isinstance(audio, (MP4, ID3)):
    print(f"Unsupported format: {file_path}")
    return False
```

### Error Handling

**Pattern**: NEVER use bare except
```python
# WRONG:
try:
    operation()
except Exception:
    pass  # Silent failure

# RIGHT:
try:
    operation()
except SpecificError as e:
    print(f"Failed to {operation} on {file}: {e}")
    return False
```

**Pattern**: Return False/None on failure, raise on programming errors
```python
def process_file(path):
    if not os.path.exists(path):
        return False  # Expected failure

    if invalid_type(path):
        raise ValueError(f"Invalid type")  # Programming error
```

### Data Ownership Tracking

**Critical Pattern**: Always check source before removing data
```python
# Get tags with source information
db_tags = get_track_tags(track_id)
db_tag_dict = {tag['tag_name']: tag['source'] for tag in db_tags}

# Only remove if source matches
for tag in tags_to_remove:
    if db_tag_dict.get(tag) == 'file':
        remove_tag(track_id, tag)
    # else: Preserve user/AI tags
```

### Background Threading

**Pattern**: Always wrap thread target in try/except
```python
def _background_worker(config):
    try:
        # Do work
        operation(config)
    except Exception as e:
        print(f"⚠️  Background operation failed: {e}")
        # Never let exception kill thread silently

thread = threading.Thread(
    target=_background_worker,
    args=(config,),
    daemon=True,
    name="DescriptiveThreadName"
)
thread.start()
```

**Note**: SQLite connections are not thread-safe, create new connection in thread

### Progress Reporting

**Pattern**: Scale with data size (percentage-based, not fixed intervals)
```python
total = len(items)
progress_interval = max(1, total // 100)  # Every 1%

for i, item in enumerate(items, 1):
    process(item)
    if show_progress and i % progress_interval == 0:
        percent = (i * 100) // total
        print(f"  Processed {percent}% ({i}/{total})...")
```

## Common Pitfalls & Solutions

### Pitfall 1: Data Loss in Bidirectional Sync
**Problem**: Removing all database records not in file deletes user data

**Solution**: Track data source, only remove owned data
```python
if tag_source == 'file':
    remove_tag(track_id, tag)  # Safe to remove
```

### Pitfall 2: File Corruption on Crash
**Problem**: Direct file writes can corrupt on interruption

**Solution**: Atomic writes (copy → modify temp → rename)
```python
import shutil

temp_path = file_path + '.tmp'
shutil.copy2(file_path, temp_path)  # Copy original to temp
audio = MutagenFile(temp_path)      # Load temp file
audio.save()                         # Save in place
os.replace(temp_path, file_path)    # Atomic replace
```

### Pitfall 3: Race Conditions in mtime Tracking
**Problem**: Getting mtime at wrong time misses changes

**Solution**: Get mtime AFTER write operation
```python
write_tags_to_file(path, tags)
current_mtime = get_file_mtime(path)  # After write
update_database(track_id, current_mtime)
```

### Pitfall 4: Lost Precision in Timestamps
**Problem**: `int(os.path.getmtime())` loses sub-second precision

**Solution**: Use float directly
```python
# Before: int(os.path.getmtime(path))  # Loses precision
# After: os.path.getmtime(path)  # Float with microsecond precision
```

### Pitfall 5: Duplicate Tags
**Problem**: File contains "mm:tag1, mm:tag1" and both get added

**Solution**: Deduplicate with set
```python
tags_set = set()
for tag in tags_from_file:
    tags_set.add(tag.lower())
return list(tags_set)
```

## Testing Strategy

### Test Script Pattern
```python
#!/usr/bin/env python3
"""Test description"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_feature():
    # Setup
    test_data = create_test_data()

    # Execute
    result = function_under_test(test_data)

    # Assert
    assert result == expected, f"Failed: {result}"
    print("  ✅ PASSED: Test description")

def main():
    tests = [test_feature]
    passed = sum(1 for t in tests if t())
    print(f"Results: {passed}/{len(tests)} passed")

if __name__ == "__main__":
    main()
```

### What to Test
- **Critical**: Data loss scenarios (ownership, removal logic)
- **Critical**: File corruption scenarios (atomic writes)
- **Important**: Edge cases (empty files, unsupported formats, duplicates)
- **Important**: Performance at scale (100+ items)

## Code Review Checklist

When reviewing sync/database code:

- [ ] Are all database operations using batch updates where possible?
- [ ] Are all file writes atomic (temp + rename)?
- [ ] Is data ownership checked before removal?
- [ ] Are there any bare `except:` blocks?
- [ ] Are errors logged with context (file, operation, cause)?
- [ ] Are timestamps stored as floats (not ints)?
- [ ] Is file format validated before operations?
- [ ] Are duplicates handled/deduplicated?
- [ ] Is progress reporting scaled to data size?
- [ ] Are background threads wrapped in try/except?

## Performance Optimization Patterns

### Before Optimizing
1. Profile first - measure actual bottleneck
2. Test with realistic data size (5000+ tracks)
3. Measure improvement after change

### Common Optimizations

**Batch Database Operations**
```python
# Before: 1000 separate commits
for item in items:
    conn.execute("UPDATE ...")
    conn.commit()  # Slow!

# After: Single commit
for item in items:
    conn.execute("UPDATE ...")
conn.commit()  # Fast!
```

**Use executemany for Bulk Updates**
```python
# 30% faster for large datasets
updates = [(value, id) for value, id in data]
conn.executemany("UPDATE table SET col = ? WHERE id = ?", updates)
```

**Avoid Redundant File Stats**
```python
# Before: Check mtime for all files
for file in all_files:
    if mtime_changed(file):
        process(file)

# After: Query only potentially changed
changed_files = get_changed_files_from_db()
for file in changed_files:
    process(file)
```

## Documentation Standards

### Code Comments
```python
# CRITICAL: Explain why something is important
# TODO: Mark future work clearly
# FIX: Mark known issues
# Note: Context or assumptions
```

### Function Docstrings
```python
def function(param: type) -> return_type:
    """Brief description of what function does.

    Detailed explanation if needed.

    Args:
        param: Description of parameter

    Returns:
        Description of return value

    Raises:
        ErrorType: When and why this error occurs
    """
```

### Update Plan Document
After implementing features or fixing bugs:
1. Update `docs/playlist-system-plan.md` with:
   - What was implemented
   - What was learned
   - What was deferred and why
   - Metrics (time, lines changed, etc.)

## Schema Management

### Current Schema Version: 7

**Version History**:
- v1-2: Initial schema
- v3: Added playlist tables (Phase 1)
- v4-5: Playlist enhancements
- v6: Playback state tracking
- v7: Sync tracking (file_mtime, last_synced_at)

### Adding Columns Pattern
```python
try:
    conn.execute("ALTER TABLE tracks ADD COLUMN new_col TYPE")
except sqlite3.OperationalError as e:
    if "duplicate column" not in str(e).lower():
        raise  # Real error, not idempotent re-run
```

**Note**: SQLite's INTEGER columns accept floats due to dynamic typing

## Module Dependencies

```
main.py
  ├── database.py (lowest level)
  ├── config.py
  ├── sync.py
  │     └── database.py
  ├── playlist.py
  │     └── database.py
  └── playlist_filters.py
        └── database.py
```

**Rule**: Modules should only import from lower levels, no circular deps

## Configuration

**Location**: `~/.config/music-minion/config.toml`

**Key Sections**:
- `[music]` - Library paths
- `[sync]` - Sync settings (auto_sync, tag_prefix, etc.)
- `[playlists]` - Playlist export settings
- `[ui]` - Dashboard settings

**Default Values**: Defined in `config.py` dataclasses

## AI Integration Patterns

### Natural Language Parsing
**Pattern**: Use structured JSON schema in prompts, not free-form
```python
# Provide exact field names, operators, and output format
system_prompt = """
Parse playlist description into filter rules.
Available fields: title, artist, album, ...
Return JSON array: [{"field": "...", "operator": "...", "value": "..."}]
"""
```

**Learning**: Structured prompts eliminate hallucinations. AI never invents invalid fields when schema is explicit.

### Two-Stage Validation
**Pattern**: Parse first, validate second
```python
# 1. Parse AI response to JSON
filters = json.loads(response)

# 2. Validate structure (keys, types)
for f in filters:
    if not all(k in f for k in ['field', 'operator', 'value']):
        raise ValueError("Missing keys")

# 3. Validate business rules with existing validator
for f in filters:
    validate_filter(f['field'], f['operator'], f['value'])
```

**Learning**: Don't trust AI output blindly. Validation catches errors early with clear feedback.

### Interactive Editor Pattern
**Pattern**: REPL-style numbered list editor
```
Current filters:
1. genre equals "dubstep"
2. year >= 2025

Commands: edit <n>, remove <n>, add, done
> edit 1
```

**Learning**: Users need control to correct AI mistakes. Numbered commands are intuitive.

## Import/Export Patterns

### Multi-Layered Path Resolution
**Pattern**: Try multiple resolution strategies
```python
def resolve_path(track_path, playlist_dir, library_root):
    # 1. Absolute path
    if Path(track_path).is_absolute() and Path(track_path).exists():
        return track_path

    # 2. Relative to playlist directory
    path = playlist_dir / track_path
    if path.exists():
        return path

    # 3. Relative to library root
    path = library_root / track_path
    if path.exists():
        return path

    # 4. URL decode (handle %20, etc.)
    decoded = urllib.parse.unquote(track_path)
    # ... try again

    # 5. Extract music structure from Windows paths
    # Look for "Music", "iTunes", "Serato" in path
```

**Learning**: Real-world playlists have inconsistent path formats. Multi-layered resolution handles cross-platform compatibility.

### Format Auto-Detection
**Pattern**: Detect by extension, validate by content
```python
def detect_format(file_path):
    ext = Path(file_path).suffix.lower()
    if ext in ['.m3u', '.m3u8']:
        return 'm3u'
    elif ext == '.crate':
        return 'serato'
    else:
        raise ValueError(f"Unsupported format: {ext}")
```

**Learning**: Extension-based detection is fast and sufficient for most cases.

### Silent Failure for Auto-Operations
**Pattern**: Auto-operations fail gracefully, never block workflow
```python
def auto_export_if_enabled(config, playlist_id):
    if not config.playlists.auto_export:
        return

    try:
        export_playlist(playlist_id, ...)
    except Exception as e:
        # Silent failure - user can manually export
        pass  # Or log to debug file
```

**Learning**: Auto-features are convenience, not requirements. Silent failure prevents interruption.

## Playback State Management

### Global State with Singleton Pattern
**Pattern**: Use database constraint for singleton
```sql
CREATE TABLE playback_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    shuffle_enabled BOOLEAN DEFAULT 0
);
```

**Learning**: Database-enforced singleton is simpler than application-level state management. Persists across sessions automatically.

### Dual Tracking Pattern
**Pattern**: Store both stable ID and position
```python
# Track both for robustness
last_played_track_id = 123  # Stable across reorders
last_played_position = 5    # Fallback if track removed
```

**Learning**: ID handles normal case, position handles edge cases (track deleted/reordered).

## Critical Learnings from Phase 7 Code Review

### 1. Data Loss Prevention Through Ownership Tracking

**CRITICAL**: When implementing bidirectional sync, data ownership/source tracking is non-negotiable.

**Pattern**:
```python
# NEVER remove data without checking ownership
for tag in tags_to_remove:
    tag_source = db_tag_dict.get(tag)
    if tag_source == 'file':  # Only remove file-sourced data
        remove_tag(track_id, tag)
    # else: Preserve user/AI data
```

**Learning**: Always check `source` field before removing data. Bidirectional sync without ownership tracking WILL cause data loss.

**Applied To**: Tag sync, ratings, playlist changes, any data that can be modified externally.

### 2. Atomic Operations Prevent Corruption

**CRITICAL**: File operations modifying user data MUST be atomic. Mutagen requires target file to exist.

**Pattern**:
```python
import shutil

temp_path = file_path + '.tmp'
try:
    shutil.copy2(file_path, temp_path)  # Copy original to temp
    audio = MutagenFile(temp_path)      # Load temp file
    # ... modify audio tags ...
    audio.save()                         # Save in place (no filename)
    os.replace(temp_path, file_path)    # Atomic replace on Unix/Windows
except Exception:
    if os.path.exists(temp_path):
        os.remove(temp_path)
    raise
```

**Why**: Crashes during write corrupt metadata permanently. No recovery possible without atomic writes.

**Learning**: `os.replace()` is atomic on both Unix and Windows. Mutagen's `save(filename)` expects the file to exist (opens with 'rb+' mode), so copy first, then modify the temp file in place.

### 3. Race Conditions in Change Detection

**CRITICAL**: Order of operations matters for consistency.

**Wrong Pattern**:
```python
# BUG: Get mtime before write
old_mtime = get_file_mtime(path)
write_tags_to_file(path, tags)
# External process modifies file here
save_mtime_to_db(old_mtime)  # WRONG - missed external change
```

**Correct Pattern**:
```python
# Write file
write_tags_to_file(path, tags)
# Get mtime AFTER write (captures our change)
current_mtime = get_file_mtime(path)
# Store in database
save_mtime_to_db(current_mtime)
```

**Learning**: Always get mtime AFTER write operation to capture your own changes correctly.

### 4. Batch Operations for Performance

**Critical**: Database operations should be batched, not per-item.

**Before (Slow)**:
```python
for item in items:
    conn.execute("UPDATE ...")
    conn.commit()  # 1000 commits = slow!
```

**After (Fast - 30% improvement)**:
```python
updates = []
for item in items:
    updates.append((value, id))

conn.executemany("UPDATE ...", updates)
conn.commit()  # Single commit
```

**Learning**: Single transaction vs multiple transactions = 30% performance improvement on large datasets.

### 5. Progress Reporting Should Scale

**Pattern**: Calculate interval based on total count (1% increments)
```python
total = len(items)
progress_interval = max(1, total // 100)  # Every 1%

for i, item in enumerate(items, 1):
    process(item)
    if show_progress and i % progress_interval == 0:
        percent = (i * 100) // total
        print(f"  {percent}% ({i}/{total})...")
```

**Learning**: Fixed intervals (every 100 items) provide no feedback for first 100. Percentage-based works for any size.

### 6. Error Handling Must Be Informative

**NEVER use bare except**:
```python
# WRONG - hides all errors
try:
    operation()
except Exception:
    pass

# RIGHT - informative error
try:
    operation()
except SpecificError as e:
    print(f"Failed to {operation} on {file}: {e}")
    return False
```

**Learning**: Every error should have context: what failed, where, why. Users need actionable information.

### 7. Background Threading Requires Exception Handling

**Pattern**: Wrap all thread targets in try/except
```python
def _background_worker(config):
    try:
        # Do work
        sync.sync_import(config, ...)
    except Exception as e:
        print(f"⚠️  Background sync failed: {e}")
        # NEVER let exception kill thread silently

thread = threading.Thread(
    target=_background_worker,
    args=(config,),
    daemon=True,
    name="DescriptiveThreadName"
)
thread.start()
```

**Learning**: Exceptions in threads don't propagate. Must catch and log explicitly.

**Note**: SQLite connections are not thread-safe - create new connection in thread.

### 8. Timestamp Precision Matters

**Wrong**:
```python
mtime = int(os.path.getmtime(path))  # Loses sub-second precision
```

**Right**:
```python
mtime = os.path.getmtime(path)  # Float with microsecond precision
```

**Learning**: Modern filesystems support nanosecond mtime. Rapid edits can have same integer timestamp. SQLite's INTEGER columns handle floats due to dynamic typing.

### 9. Validation Should Fail Fast

**Pattern**: Validate at entry point, not during processing
```python
def process_file(file_path):
    # Validate format FIRST
    audio = MutagenFile(file_path, easy=False)
    if not isinstance(audio, (MP4, ID3)):
        print(f"Unsupported format: {file_path}")
        return False

    # Now safe to process
    process_audio(audio)
```

**Learning**: Explicit validation + clear error = better UX. Don't rely on silent failures.

### 10. Comments Are Critical for Safety

**Pattern**: Mark critical sections with CRITICAL/TODO/FIX
```python
# CRITICAL: Only remove tags where source='file'
# This prevents data loss of user-created and AI-generated tags.
for tag in tags_to_remove:
    if db_tag_dict.get(tag) == 'file':
        remove_tag(track_id, tag)
```

**Learning**: Explain WHY, not just WHAT. Future developers (including yourself) need context.

## Future Phase Priorities

Based on Phase 7 learnings:

1. **Phase 8 (Polish)**:
   - File watching (watchdog library)
   - Conflict detection UI
   - Comprehensive test suite
   - Performance monitoring

2. **Security Hardening**:
   - Path traversal prevention
   - Tag content sanitization
   - Permission validation

3. **Monitoring**:
   - Structured logging
   - Error rate tracking
   - Performance metrics

---

**Last Updated**: 2025-10-01 after architecture refactoring and blessed UI implementation

## Architecture Refactoring (2025-10-01)

### Layered Architecture with Functional Patterns

**Decision**: Reorganized flat file structure into layered architecture with domain-driven design

**Before**: All modules in `src/music_minion/` (player.py, library.py, playlist.py, etc.)

**After**: Organized into layers:
```
src/music_minion/
├── core/           # Infrastructure (config, database, console)
├── domain/         # Business logic (library, playback, playlists, sync, ai)
├── commands/       # Command handlers (pure functions taking AppContext)
├── ui/             # User interface (blessed UI)
└── utils/          # Utilities (parsers, autocomplete)
```

**Benefits**:
- ✅ Clear separation of concerns
- ✅ Easier to navigate and understand
- ✅ Natural import boundaries (no circular dependencies)
- ✅ Modules grouped by domain instead of technical layer
- ✅ Easier to test (domain logic isolated from UI/infrastructure)

**Pattern**: Each domain has `__init__.py` that re-exports public API
```python
# domain/playlists/__init__.py
from .crud import create_playlist, get_playlists
from .filters import apply_filters

# Usage in commands/
from ..domain import playlists
playlists.create_playlist(...)
```

**Learning**: Layered architecture scales better than flat structure. Group by domain (playlists, playback), not by type (models, services).

### AppContext Pattern for Explicit State Passing

**Decision**: Replace global variables with `AppContext` dataclass passed explicitly

**Before**: Global mutable state accessed via imports
```python
# main.py
current_player_state = PlayerState()
music_tracks = []

# other_module.py
from main import current_player_state  # Import hack!
current_player_state.is_playing = True  # Hidden mutation
```

**After**: Immutable context passed explicitly
```python
@dataclass
class AppContext:
    config: Config
    music_tracks: List[Track]
    player_state: PlayerState
    console: Console

    def with_player_state(self, state: PlayerState) -> 'AppContext':
        return AppContext(self.config, self.music_tracks, state, self.console)

# Command handlers
def handle_play(ctx: AppContext, args: list) -> tuple[AppContext, bool]:
    new_player_state = start_playback(ctx.player_state)
    new_ctx = ctx.with_player_state(new_player_state)
    return new_ctx, True
```

**Benefits**:
- ✅ Explicit data flow (no hidden mutations)
- ✅ Easier testing (pure functions)
- ✅ No import hacks to access global state
- ✅ Immutable updates prevent subtle bugs
- ✅ Clear context boundaries (what functions need what data)

**Pattern**: Command handler signature
```python
def handle_command(ctx: AppContext, command: str, args: list) -> tuple[AppContext, bool]:
    # Returns: (new_context, should_continue)
    pass
```

**Learning**: Explicit state passing > global variables. Functions that take context and return new context are easier to reason about, test, and maintain.

### Helper Functions for Context Transitions

**Decision**: Create helpers for context ↔ globals during transition period

**Pattern**: Bidirectional sync during migration
```python
# helpers.py
def create_context_from_globals() -> AppContext:
    """Convert global state to AppContext."""
    return AppContext(
        config=current_config,
        music_tracks=music_tracks,
        player_state=current_player_state,
        console=console
    )

def sync_context_to_globals(ctx: AppContext) -> None:
    """Sync AppContext back to globals (for legacy code)."""
    global current_config, music_tracks, current_player_state
    current_config = ctx.config
    music_tracks = ctx.music_tracks
    current_player_state = ctx.player_state
```

**Benefits**:
- ✅ Gradual migration (both patterns work)
- ✅ Blessed UI uses AppContext fully
- ✅ Legacy dashboard mode still works
- ✅ Clear path forward (remove globals eventually)

**Learning**: Helper functions enable gradual refactoring. Don't try to refactor everything at once - create bridges between old and new patterns.

## blessed UI Implementation (Tasks 1-8 Complete)

### Architecture Decision: Pure Functions + Immutable State

**Pattern**: Functional approach with blessed (lower-level than Textual)

```
ui_blessed/
├── state.py              # Immutable state with dataclasses.replace()
├── main.py               # Event loop
├── rendering/            # Pure rendering functions
│   ├── dashboard.py
│   ├── history.py
│   ├── input.py
│   ├── palette.py
│   └── layout.py
├── events/               # Event handlers
│   ├── keyboard.py
│   └── commands.py
└── data/                 # Static data and utilities
    ├── palette.py
    └── formatting.py
```

### Key Patterns

#### 1. Immutable State Updates
**Pattern**: All state transformations return new instances
```python
def append_input_char(state: UIState, char: str) -> UIState:
    from dataclasses import replace
    new_text = state.input_text + char
    return replace(state, input_text=new_text, cursor_pos=len(new_text))
```

**Learning**: Immutable updates make state changes traceable and testable. Use `dataclasses.replace()` instead of mutation.

#### 2. Pure Rendering Functions
**Pattern**: Render functions take terminal, state, position - no side effects except terminal output
```python
def render_dashboard(term: Terminal, state: UIState, y_start: int) -> int:
    lines = []
    # Build lines from state
    for i, line in enumerate(lines):
        print(term.move_xy(0, y_start + i) + line)
    return len(lines)  # Height used
```

**Learning**: Pure functions = easier testing. Return heights for layout calculations.

#### 3. Terminal Color Application
**Pattern**: blessed colors are functions that wrap strings
```python
# Build colored text by chaining function calls
header = (
    term.bold_magenta(ICONS['music']) + " " +
    term.bold_cyan("MUSIC") + " " +
    term.bold_blue("MINION")
)
```

**Learning**: blessed colors compose naturally. Build strings incrementally, apply colors per-segment.

#### 4. Dynamic Layout Calculation
**Pattern**: Calculate all positions in single function
```python
def calculate_layout(term: Terminal, state: UIState) -> dict[str, int]:
    dashboard_height = 20
    input_height = 3
    palette_height = 22 if state.palette_visible else 0
    
    return {
        'dashboard_y': 0,
        'history_y': dashboard_height,
        'history_height': term.height - dashboard_height - input_height - palette_height,
        'input_y': term.height - input_height - palette_height,
        'palette_y': term.height - palette_height,
    }
```

**Learning**: Single layout function makes position logic visible. Heights adjust based on state (palette visible/hidden).

#### 5. Keyboard Event Parsing
**Pattern**: Two-stage processing - parse then handle
```python
def parse_key(key: Keystroke) -> dict:
    # Normalize various key representations
    if key.name == 'KEY_ENTER':
        return {'type': 'enter'}
    elif key == '\x03':  # Ctrl+C
        return {'type': 'ctrl_c'}
    # ...
    
def handle_key(state: UIState, key: Keystroke) -> tuple[UIState, str | None]:
    event = parse_key(key)
    # Handle by event type
    if event['type'] == 'ctrl_c':
        return state, 'QUIT'
    # ...
```

**Learning**: Separate parsing (normalization) from handling (business logic). Returns (new_state, command_or_none).

#### 6. Live Palette Filtering
**Pattern**: Update filtered items on every keypress
```python
if event['type'] == 'char':
    state = append_input_char(state, char)
    
    if state.palette_visible:
        query = state.input_text[1:]  # Remove "/" prefix
        filtered = filter_commands(query, COMMAND_DEFINITIONS)
        state = update_palette_filter(state, query, filtered)
```

**Learning**: Instant feedback feels responsive. Filter on command name only for predictable results.

#### 7. Box Drawing Characters
**Pattern**: Use Unicode box-drawing for borders
```python
# Top border
border = "─" * (term.width - 2)
print(term.cyan(f"┌{border}┐"))

# Side borders
print(term.cyan("│ ") + content + term.cyan(" │"))

# Bottom border
print(term.cyan(f"└{border}┘"))
```

**Learning**: `┌─┐│└┘` look better than ASCII `+-|`. Terminals support Unicode.

#### 8. Cursor Positioning
**Pattern**: Use `term.move_xy(x, y)` before each line
```python
for i, line in enumerate(lines):
    print(term.move_xy(0, y_start + i) + line)
```

**Learning**: Explicit positioning prevents line wrap issues. Always move before printing.

### blessed Benefits

**Why blessed**:
- ✅ Lightweight (no framework overhead)
- ✅ Full control over rendering
- ✅ Easier to reason about (explicit state flow)
- ✅ No "magic" - direct terminal control
- ✅ Functional programming style (pure functions)

**Trade-offs**:
- Requires manual flickering prevention
- More explicit rendering code
- No built-in widgets (build what you need)

**Decision**: blessed fits the functional programming philosophy and provides full control without framework complexity.

### Terminal Color Notes

blessed color names:
- Basic: `black`, `red`, `green`, `yellow`, `blue`, `magenta`, `cyan`, `white`
- Bright: `bright_red`, `bright_green`, etc.
- Modifiers: `bold`, `dim`, `italic`, `underline`
- Backgrounds: `on_black`, `on_red`, `bold_white_on_blue`, etc.

**Learning**: Combine with underscores: `term.bold_bright_red_on_black("text")`

### Progress Bar Gradient Pattern

**Pattern**: Apply different colors based on percentage
```python
for i in range(filled):
    char_percentage = (i + 1) / bar_width
    if char_percentage < 0.33:
        progress_parts.append(term.green("█"))
    elif char_percentage < 0.66:
        progress_parts.append(term.yellow("█"))
    else:
        progress_parts.append(term.red("█"))
```

**Learning**: Character-by-character coloring creates smooth gradients. Use block characters `█░` for solid look.

### Command Palette Selection Highlighting

**Pattern**: Use inverted colors for selected item
```python
if is_selected:
    item_line = term.black_on_cyan(f"  {icon} {cmd:<20} {desc}")
else:
    item_line = term.cyan(cmd) + term.dim(desc)
```

**Learning**: Background color (not just bold) makes selection obvious. Consistent padding aligns columns.

### State Update Function Naming

**Pattern**: Verb-noun naming for clarity
```python
# Good: Clear action
append_input_char(state, char)
delete_input_char(state)
set_input_text(state, text)
show_palette(state)
hide_palette(state)

# Bad: Unclear
modify_input(state, 'append', char)
palette_state(state, True)
```

**Learning**: Specific function names > generic functions with mode parameter. More functions, clearer intent.

### Event Handling Return Pattern

**Pattern**: Return (new_state, optional_command)
```python
def handle_key(state, key) -> tuple[UIState, str | None]:
    # Most events: update state only
    if event['type'] == 'char':
        state = append_input_char(state, char)
        return state, None
    
    # Some events: update state AND trigger command
    if event['type'] == 'enter':
        command = state.input_text
        state = set_input_text(state, "")
        return state, command
```

**Learning**: Tuple return allows state updates + optional side effects. `None` means no command to execute.

## AI Review System Patterns (2025-10-03)

### Conversational Tag Feedback Loop

**Pattern**: Interactive conversation mode for tag review
```python
def ai_review_loop(term: Terminal, track_id: int, ctx: AppContext) -> None:
    # Load current tags with reasoning
    tags = get_track_tags(track_id)

    # Display tags and enter conversation mode
    conversation_history = []

    while True:
        user_input = get_user_input(term)

        if user_input == "done":
            break

        # Add to conversation history
        conversation_history.append({"role": "user", "content": user_input})

        # Get AI response with tag regeneration
        response = ai_chat_with_context(conversation_history, track_metadata, tags)

        # Extract new tags from response
        new_tags = parse_tags_from_response(response)

        # Show preview, ask for confirmation
        if confirm_tags(term, new_tags):
            save_tags(track_id, new_tags)
            break
```

**Key Elements**:
- Conversation history maintains context
- Tags included in every prompt for reference
- "done" keyword exits conversation
- Preview before saving changes
- Extract learnings after successful review

### Learning Extraction and Categorization

**Pattern**: AI extracts structured learnings from conversation
```python
def extract_learnings(conversation_history: list) -> dict:
    prompt = f"""
    Analyze this conversation and extract learnings:

    Categories:
    - Rules: Things to never tag
    - Good Vocabulary: Approved terms and their meanings
    - Bad Vocabulary: Terms to avoid and why
    - Genre Guidance: Genre-specific tagging rules

    Return as structured markdown.
    """

    learnings_md = call_ai(prompt + conversation_history)
    append_to_learnings_file(learnings_md)
```

**Learning**: AI is good at categorizing feedback. Provide clear categories and it will structure learnings appropriately.

### Prompt Versioning and Enhancement

**Pattern**: Version control for AI prompts with testing
```python
def enhance_prompt(current_prompt: str, learnings: str) -> str:
    # AI proposes improved prompt
    proposal = ai_suggest_prompt_improvement(current_prompt, learnings)

    # Test on sample tracks
    test_tracks = get_random_tracks(3)

    before_results = []
    after_results = []

    for track in test_tracks:
        before = analyze_with_prompt(track, current_prompt)
        after = analyze_with_prompt(track, proposal)

        before_results.append(before)
        after_results.append(after)

    # Show diff and results
    display_prompt_diff(current_prompt, proposal)
    display_test_comparison(before_results, after_results)

    # User confirms
    if confirm("Accept new prompt?"):
        save_prompt_version(proposal)
        return proposal

    return current_prompt
```

**Key Elements**:
- Versioned prompts with timestamps
- Test on real data before adopting
- Show before/after comparison
- Preserve history for rollback
- Active prompt symlink

**Learning**: Always test prompt changes on real data. Theoretical improvements may not work in practice.

### Reasoning Storage Pattern

**Pattern**: Store AI explanations alongside tags
```python
# Database schema
"""
ALTER TABLE tags ADD COLUMN reasoning TEXT;
"""

# Usage
def add_tags_with_reasoning(track_id: int, tags_dict: dict):
    # tags_dict = {"energetic": "Fast tempo (140 BPM)", ...}
    for tag, reasoning in tags_dict.items():
        conn.execute(
            "INSERT INTO tags (track_id, tag_name, source, reasoning) VALUES (?, ?, ?, ?)",
            (track_id, tag, 'ai', reasoning)
        )
```

**Benefits**:
- Transparency: User sees why AI chose each tag
- Debugging: Identify prompt issues from reasoning
- Learning: Reasoning informs prompt improvements
- Context: Future AI can see past decisions

**Learning**: Reasoning is critical for iterative improvement. Without it, you can't understand why AI made decisions.

## Hot-Reload Development Patterns (2025-10-03)

### Watchdog-Based File Monitoring

**Pattern**: Background thread monitors code changes
```python
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import importlib
import sys

class CodeReloadHandler(FileSystemEventHandler):
    def __init__(self, debounce_ms=100):
        self.last_reload = {}
        self.debounce_ms = debounce_ms

    def on_modified(self, event):
        if not event.src_path.endswith('.py'):
            return

        # Debounce rapid changes
        now = time.time()
        if event.src_path in self.last_reload:
            if now - self.last_reload[event.src_path] < self.debounce_ms / 1000:
                return

        self.last_reload[event.src_path] = now

        # Reload module
        reload_module(event.src_path)

def start_hot_reload():
    observer = Observer()
    handler = CodeReloadHandler()
    observer.schedule(handler, 'src/music_minion/', recursive=True)
    observer.start()
```

**Key Elements**:
- Debouncing prevents double-reloads
- Recursive monitoring of src directory
- Background thread doesn't block main app
- Filter for .py files only

### Module Reloading Pattern

**Pattern**: Convert file paths to module names and reload
```python
def reload_module(file_path: str):
    # Convert: src/music_minion/commands/playlist.py
    # To: music_minion.commands.playlist

    module_name = (
        file_path
        .replace('src/', '')
        .replace('/', '.')
        .replace('.py', '')
    )

    if module_name not in sys.modules:
        return  # Not imported yet, skip

    try:
        importlib.reload(sys.modules[module_name])
        print(f"🔄 Reloaded: {Path(file_path).name}")
    except Exception as e:
        print(f"❌ Failed to reload {module_name}: {e}")
```

**Learning**: Only reload modules that are already imported. New files require first-time import via normal command execution.

### State Preservation Pattern

**Pattern**: Preserve critical state across reloads
```python
# In main.py - state stored in function scope
def main():
    # These persist across module reloads
    ctx = AppContext(...)
    terminal = Terminal()

    while True:
        # Code reloads don't affect ctx or terminal
        command = get_command()

        # This module might get reloaded mid-execution
        from music_minion.router import route_command

        # But state persists
        ctx, should_continue = route_command(ctx, command)
```

**Learning**: Function-scoped variables in main loop survive module reloads. Global variables in reloaded modules get reset.

## Advanced UI Component Patterns

### Track Viewer Navigation

**Pattern**: Scrollable list with vim-like keybindings
```python
@dataclass(frozen=True)
class TrackViewerState:
    tracks: List[Track]
    selected_index: int = 0
    scroll_offset: int = 0
    visible_height: int = 20

def handle_track_viewer_key(state: TrackViewerState, key: str) -> TrackViewerState:
    if key == 'j':  # Down
        new_index = min(state.selected_index + 1, len(state.tracks) - 1)
        return move_selection(state, new_index)

    elif key == 'k':  # Up
        new_index = max(state.selected_index - 1, 0)
        return move_selection(state, new_index)

    elif key == '\n':  # Enter - play track
        return state  # Signal to play selected track

    return state

def move_selection(state: TrackViewerState, new_index: int) -> TrackViewerState:
    # Adjust scroll if selection goes off screen
    if new_index < state.scroll_offset:
        scroll_offset = new_index
    elif new_index >= state.scroll_offset + state.visible_height:
        scroll_offset = new_index - state.visible_height + 1
    else:
        scroll_offset = state.scroll_offset

    return dataclasses.replace(
        state,
        selected_index=new_index,
        scroll_offset=scroll_offset
    )
```

**Learning**: Track both selection and scroll position. Auto-scroll when selection moves off-screen.

### Analytics Viewer Scrolling Bug (Two-Part Fix)

**Issue**: Analytics viewer j/k scrolling wasn't working

#### Part 1: Height Parameter Mismatch
**Root Cause**: Wrong height passed to scroll calculations
- Analytics viewer uses dynamic height (30+ lines based on screen size)
- Keyboard handler was receiving `palette_height` (fixed 22 lines)
- Max scroll calculation: `max_scroll = total_lines - viewer_height + 1`
- Wrong height → wrong max_scroll → scrolling disabled

**Fix**: Pass correct height parameter
```python
# app.py - extract correct height from layout
analytics_viewer_height = layout['analytics_viewer_height'] if layout else 30
ui_state, command_line = handle_key(ui_state, key, palette_height, analytics_viewer_height)
```

#### Part 2: State Tracking Bug (The Real Cause!)
**Root Cause**: Inconsistent palette_state tuple sizes prevented change detection
- Line 298: Initial value had 7 elements (missing analytics fields)
- Line 338: Comparison had 7 elements (missing analytics fields)
- Line 422: Update had 9 elements (included analytics fields)
- Line 485: Update had 7 elements (missing analytics fields)

When j/k pressed:
1. ✅ Scroll offset changed in state
2. ❌ Comparison tuple didn't include scroll offset
3. ❌ Change not detected
4. ❌ No redraw triggered
5. ❌ Screen didn't update

**Fix**: Make all palette_state tuples consistent (9 elements)
```python
# All three locations now have same 9-element tuple:
last_palette_state = (
    ui_state.palette_visible,
    ui_state.palette_selected,
    ui_state.confirmation_active,
    ui_state.wizard_active,
    ui_state.wizard_selected,
    ui_state.track_viewer_visible,
    ui_state.track_viewer_selected,
    ui_state.analytics_viewer_visible,  # Added
    ui_state.analytics_viewer_scroll     # Added
)
```

**Learning**:
- **State tracking tuples must be consistent across all code paths**
- Missing fields in comparison prevents change detection
- State can change, but UI won't redraw without change detection
- Always verify initial value, comparison, and all update sites match
- Height parameters must match the actual rendered height for scroll calculations
- Don't reuse height parameters across different UI components with different sizes

### Wizard Multi-Step Flow Pattern

**Pattern**: State machine for multi-step processes
```python
@dataclass(frozen=True)
class WizardState:
    step: int = 0
    data: dict = field(default_factory=dict)
    complete: bool = False

def wizard_step_handler(state: WizardState, user_input: str) -> WizardState:
    if state.step == 0:
        # Step 1: Get playlist name
        data = {**state.data, 'name': user_input}
        return dataclasses.replace(state, step=1, data=data)

    elif state.step == 1:
        # Step 2: Get field to filter
        data = {**state.data, 'field': user_input}
        return dataclasses.replace(state, step=2, data=data)

    # ... more steps

    elif state.step == 5:
        # Final step
        return dataclasses.replace(state, complete=True)
```

**Learning**: State machine pattern works well for wizards. Each step validates and advances. Immutable updates make it easy to add "back" functionality.

### InternalCommand Pattern

**Pattern**: Type-safe UI commands separate from user commands
```python
@dataclass(frozen=True)
class InternalCommand:
    action: str
    data: dict = field(default_factory=dict)

# Type-safe constructors
def show_track_viewer(playlist_id: int) -> InternalCommand:
    return InternalCommand('show_track_viewer', {'playlist_id': playlist_id})

def close_track_viewer() -> InternalCommand:
    return InternalCommand('close_track_viewer')

# Handler
def handle_internal_command(state: UIState, cmd: InternalCommand) -> UIState:
    if cmd.action == 'show_track_viewer':
        tracks = load_playlist_tracks(cmd.data['playlist_id'])
        viewer_state = TrackViewerState(tracks=tracks)
        return dataclasses.replace(state, track_viewer=viewer_state)

    elif cmd.action == 'close_track_viewer':
        return dataclasses.replace(state, track_viewer=None)
```

**Benefits**:
- Type safety vs string commands
- Clear API for UI interactions
- Easy to find all usages (grep for constructor)
- Self-documenting (function name = purpose)

**Learning**: Internal commands reduce bugs from typos in string literals. Constructor functions provide type safety and discoverability.

### Command History Management

**Pattern**: Circular buffer with arrow key navigation
```python
@dataclass(frozen=True)
class UIState:
    command_history: List[str] = field(default_factory=list)
    history_index: int = -1  # -1 = not navigating
    input_text: str = ""
    temp_input: str = ""  # Save current input while navigating

def handle_up_arrow(state: UIState) -> UIState:
    if not state.command_history:
        return state

    # Save current input if starting navigation
    if state.history_index == -1:
        temp_input = state.input_text
    else:
        temp_input = state.temp_input

    # Navigate up in history
    new_index = min(state.history_index + 1, len(state.command_history) - 1)
    text = state.command_history[-(new_index + 1)]

    return dataclasses.replace(
        state,
        history_index=new_index,
        input_text=text,
        temp_input=temp_input
    )

def handle_down_arrow(state: UIState) -> UIState:
    if state.history_index == -1:
        return state  # Not navigating

    new_index = state.history_index - 1

    if new_index < 0:
        # Restore temp input
        return dataclasses.replace(
            state,
            history_index=-1,
            input_text=state.temp_input,
            temp_input=""
        )

    text = state.command_history[-(new_index + 1)]
    return dataclasses.replace(state, history_index=new_index, input_text=text)
```

**Learning**: Save current input when starting history navigation so user can get back to it. Use -1 to indicate "not navigating" state.

### Review Handler Event Loop

**Pattern**: Dedicated event loop for AI review conversations
```python
def ai_review_event_loop(term: Terminal, ctx: AppContext, track_id: int):
    # Enter raw mode for single-char input
    with term.raw():
        conversation = []

        while True:
            # Display current state
            render_conversation(term, conversation)

            # Get user input (full line)
            user_input = get_line_input(term)

            if user_input.lower() == 'done':
                break

            # Show thinking indicator
            print(term.move_xy(0, term.height - 1) + "🤔 Thinking...")

            # Call AI
            response = ai_chat(conversation, user_input, track_metadata)
            conversation.append({"role": "assistant", "content": response})

            # Check if AI proposed new tags
            if has_tag_proposal(response):
                new_tags = extract_tags(response)

                if confirm_tags(term, new_tags):
                    save_tags(track_id, new_tags)
                    extract_and_save_learnings(conversation)
                    break
```

**Learning**: Separate event loop for complex interactions. Clean entry/exit with context managers. Visual feedback during AI calls.

---

**Last Updated**: 2025-11-16 after track search implementation

## Track Search Implementation (2025-11-16)

### In-Memory Filtering Pattern
**Pattern**: Pre-load all data once, filter in-memory on each keystroke for instant results
```python
# Load once when search opens (100ms for 5000 tracks)
all_tracks = database.get_all_tracks_with_metadata()

# Filter on every keystroke (< 5ms)
def filter_tracks(query: str, all_tracks: list) -> list:
    query_lower = query.lower()
    return [t for t in all_tracks if query_lower in concatenated_fields(t).lower()]
```

**Benefits**:
- < 5ms filtering vs 20-50ms database queries
- Scales well to 10,000+ tracks
- Simple implementation, no complex indexing

**Learning**: For read-heavy operations with < 10K records, in-memory filtering is faster than database LIKE queries. The 100ms initial load is acceptable for instant subsequent filtering.

### SQLite GROUP_CONCAT Limitations
**Issue**: `GROUP_CONCAT(DISTINCT column, separator)` fails - SQLite doesn't support both DISTINCT and custom separator.

**Wrong**:
```python
GROUP_CONCAT(DISTINCT notes.note_text, ' ')  # ERROR: DISTINCT aggregates must have exactly one argument
```

**Right**:
```python
GROUP_CONCAT(notes.note_text, ' ')  # Remove DISTINCT, or
GROUP_CONCAT(DISTINCT notes.note_text)  # Remove separator
```

**Learning**: SQLite's GROUP_CONCAT is more limited than other databases. Check documentation before assuming feature parity.

### UI Action Protocol Pattern
**Pattern**: Use `ctx.with_ui_action()` to signal UI changes from command handlers
```python
# Command handler (non-UI layer)
def handle_search(ctx: AppContext, args: list) -> tuple[AppContext, bool]:
    all_tracks = database.get_all_tracks_with_metadata()
    ctx = ctx.with_ui_action({
        'type': 'show_track_search',
        'all_tracks': all_tracks
    })
    return ctx, True

# UI executor (UI layer)
def _handle_ui_actions(ctx: AppContext, ui_state: UIState) -> UIState:
    if action['type'] == 'show_track_search':
        all_tracks = action.get('all_tracks', [])
        ui_state = show_track_search(ui_state, all_tracks)
    return ui_state
```

**Learning**: This is the established pattern for command → UI communication. Don't try to directly manipulate UI state from command handlers - use the action protocol.

**Last Updated**: 2025-10-03 after AI review system, hot-reload, track viewer, and wizard implementation

## UI Enhancements: Scrollable History & Rich Analytics (2025-10-05)

### Command History Scrolling
**Problem**: Long analytics output exceeded visible command history area, making it impossible to review full reports.

**Solution**: Added keyboard-based scrolling for command history.

**Implementation**:
1. **State Management** (`state.py`):
   ```python
   def scroll_history_up(state, lines=10):
       new_scroll = min(state.history_scroll + lines, len(state.history) - 1)
       return replace(state, history_scroll=new_scroll)

   def add_history_line(state, text, color):
       # Auto-reset scroll to bottom on new output
       return replace(state, history=new_history, history_scroll=0)
   ```

2. **Render Logic** (`history.py`):
   ```python
   # Calculate visible window based on scroll offset
   end_idx = len(history) - scroll_offset
   start_idx = max(0, end_idx - height)
   visible_lines = history[start_idx:end_idx]
   
   # Show indicator when scrolled
   if scroll_offset > 0:
       indicator = f"↑ Scrolled ({scroll_offset}/{total} lines from bottom)"
   ```

3. **Keyboard Shortcuts** (`keyboard.py`):
   - `Page Up`: Scroll up by ~20 lines
   - `Page Down`: Scroll down by ~20 lines
   - `Home`: Jump to oldest message
   - `End`: Jump to newest message

**Behavior**:
- Scroll only works when palette/wizard/viewer not active
- Auto-scrolls to bottom when new output appears
- Visual indicator shows scroll position

**Learning**: Scroll offset from bottom (0 = newest) is more intuitive than from top for command history.

---

### Enhanced Analytics Formatting
**Problem**: Analytics output was plain text, making it hard to quickly identify trends and issues.

**Solution**: Added ASCII bar charts, color coding, and visual hierarchy using Rich library.

**Visual Enhancements**:

1. **ASCII Bar Charts**:
   ```python
   def create_ascii_bar(value, max_value, width=20):
       filled_width = int((value / max_value) * width)
       return '▓' * filled_width + '░' * (width - filled_width)
   ```

   Used for:
   - Top artists distribution
   - Genre distribution  
   - BPM range distribution
   - Quality/completeness metrics

2. **Color Coding**:
   ```python
   def get_quality_color(percentage):
       if percentage >= 80: return "bold green"  # 🟢
       if percentage >= 50: return "bold yellow" # 🟡
       return "bold red"                         # 🔴
   ```

   Applied to:
   - Quality completeness score
   - Missing metadata warnings
   - Peak BPM ranges

3. **Visual Hierarchy**:
   - Header: Rich Panel with cyan border
   - Section headers: Bold yellow with emojis
   - Data highlights: Bold white for key numbers
   - Metadata: Dim text for supporting info
   - Separators: Colored unicode lines

**Example Output**:
```
╭─────────────────────────────────────╮
│ 📊 "NYE 2025" Analytics (smart)     │
╰─────────────────────────────────────╯

📈 BASIC STATS
  Tracks: 127
  Duration: 8h 34m 12s (avg: 4m 3s)

🎤 TOP ARTISTS
  Excision             ▓▓▓▓▓▓▓▓▓▓▓▓  12 (9%)
  Subtronics           ▓▓▓▓▓▓▓▓░░░░   8 (6%)

⚡ BPM ANALYSIS
  Range: 138-174 BPM (avg: 148, median: 150)
  Distribution:
    140-160  │  62  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓ ← Peak

✅ QUALITY METRICS
  Completeness: ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░ 92% 🟢
  Missing Metadata:
    BPM   : ██████████ 3 tracks (2%)
```

**Key Patterns**:

1. **Scaling Bars**: Always scale to max value in dataset
   ```python
   max_count = max(a['track_count'] for a in top_artists)
   bar = create_ascii_bar(count, max_count, width=12)
   ```

2. **Peak Highlighting**: Mark highest value in distributions
   ```python
   style = "bold green" if count == max_count else "white"
   peak_marker = " ← Peak" if count == max_count else ""
   ```

3. **Compact vs Full**: Respect `--compact` flag for different detail levels
   ```python
   limit = 5 if compact_mode else 10
   ```

**Benefits**:
- ✅ Immediate visual pattern recognition
- ✅ Quick identification of issues (red missing data)
- ✅ Professional, organized appearance
- ✅ Scrollable to review all sections
- ✅ Color-blind friendly (uses shape + color)

**Learning**: ASCII bar charts provide significant UX improvement with minimal code complexity. Rich library markup is powerful but keep it simple.

---

### Testing Approach
**Verification**:
1. Python syntax check: `python -m py_compile <files>`
2. Module import test: Verify functions exist
3. Function unit tests: Test edge cases (empty data, max values)
4. Integration test: Run actual analytics command

**Edge Cases Handled**:
- Empty playlists (show message, don't crash)
- Division by zero in percentages
- Scroll past boundaries (clamped to valid range)
- Missing analytics sections (graceful degradation)

**Time Estimate**: ~1.5 hours actual (vs 1.75 hours planned)
- Scrolling: 30 min (as estimated)
- Rich formatting: 1 hour (as estimated)
- Testing: Concurrent with development


## SoundCloud Integration & Provider Architecture (2025-11-20)

### Multi-Provider Like Tracking Pattern
**Pattern**: Use `ratings.source` column to distinguish provider-specific like markers from user ratings
```python
# Database schema v17
ALTER TABLE ratings ADD COLUMN source TEXT DEFAULT 'user'
CREATE INDEX idx_ratings_track_source ON ratings (track_id, source)

# Check provider like status (cached in UI state)
has_soundcloud_like = database.has_soundcloud_like(track_id)

# Add provider like marker (deduplicated)
database.add_rating(track_id, 'like', 'Synced from SoundCloud', source='soundcloud')

# Smart sync: only call API if marker doesn't exist
if not has_soundcloud_like(track_id):
    provider.like_track(state, soundcloud_id)
    add_rating(track_id, 'like', context, source='soundcloud')
```

**Benefits**:
- ✅ One API call per track (checked via marker existence)
- ✅ User can like track multiple times locally (temporal data)
- ✅ Provider likes are binary state (one marker per provider)
- ✅ Extensible to multiple providers (spotify, youtube)

**Learning**: Separate user ratings (temporal, multiple) from provider sync state (binary, single marker). The marker pattern prevents duplicate API calls while preserving local rating history.

### Provider Module Refactoring Pattern
**Pattern**: Split large provider files into focused modules
```
providers/soundcloud/
  ├── __init__.py       # Re-exports all public functions
  ├── auth.py           # OAuth 2.0 + PKCE, token management (self-contained)
  └── api.py            # API operations (imports from auth.py)
```

**Benefits**:
- ✅ ~200-300 lines per file vs 1000+ monolithic
- ✅ Clear separation: auth (credentials) vs api (operations)
- ✅ No circular imports (auth is self-contained, api imports auth)

**Learning**: Refactor providers when reaching ~600+ lines. Split by concern (auth vs api) not by feature. Auth module should have zero dependencies on api module.

### UI State Caching for Database Queries
**Pattern**: Cache frequently-accessed database flags in UIState to avoid repeated queries
```python
@dataclass
class UIState:
    current_track_has_soundcloud_like: bool = False  # Cached

# Update when track changes (full redraw)
has_sc_like = database.has_soundcloud_like(track_id)
ui_state = replace(ui_state, current_track_has_soundcloud_like=has_sc_like)

# Render uses cached value (no database query)
heart = term.red(' ♥') if ui_state.current_track_has_soundcloud_like else ""
```

**Benefits**:
- ✅ No database query on every render (60+ times per minute during playback)
- ✅ Consistent with partial rendering strategy
- ✅ Simple boolean flag vs complex query result

**Learning**: Cache any database-derived UI flags in UIState, update during full redraws only. Partial renders should never query database.

### Batch Like Sync with Progress Reporting
**Pattern**: Sync thousands of provider likes efficiently with progress feedback
```python
# Fetch ALL liked track IDs (paginated, 200 at a time)
all_liked_ids = set()
while url:
    response = requests.get(url, params={'limit': 200})
    for item in response.json()['collection']:
        all_liked_ids.add(str(item['id']))
    if total % 200 == 0:
        print(f"  Fetching likes: {total}...")

# Single batch insert for all markers
track_ids = get_matching_db_tracks(all_liked_ids)  # One query
inserted = database.batch_add_soundcloud_likes(track_ids)  # executemany()
```

**Benefits**:
- ✅ API calls are slow (200 tracks at a time), show progress
- ✅ Database insert is fast (executemany), one transaction
- ✅ Syncs markers for existing tracks, not just new imports

**Learning**: Separate API fetch (slow, progress reporting) from database insert (fast, batch operation). Progress on API calls, not database operations.

---

## Centralized Logging Implementation (2025-11-20)

### Logging Setup Pattern
**Pattern**: Initialize logging once at application startup from config
```python
# core/logging.py - Centralized setup
from logging.handlers import RotatingFileHandler

def setup_logging(level: str, log_file_path: Optional[Path], max_bytes: int, backup_count: int, console_output: bool):
    log_file = log_file_path or get_data_dir() / "music-minion.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    root_logger.handlers.clear()  # Remove existing handlers

    # File handler with rotation
    file_handler = RotatingFileHandler(log_file, maxBytes=max_bytes, backupCount=backup_count)
    file_handler.setFormatter(logging.Formatter(
        fmt='%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))
    root_logger.addHandler(file_handler)

# main.py - Initialize at startup
mm_logging.setup_logging(
    level=config.logging.level,
    log_file_path=Path(config.logging.log_file) if config.logging.log_file else None,
    max_bytes=config.logging.max_file_size_mb * 1024 * 1024,
    backup_count=config.logging.backup_count,
    console_output=config.logging.console_output
)
```

**Benefits**:
- ✅ Single initialization point (main.py startup)
- ✅ All modules automatically log to file via `logging.getLogger(__name__)`
- ✅ Automatic log rotation (default: 10MB, 5 backups)
- ✅ Configurable via config.toml
- ✅ Clear handlers before setup prevents duplicate logs

**Learning**: Configure root logger at startup, then all modules use `logging.getLogger(__name__)` - no per-module configuration needed. Clearing handlers prevents duplicates on hot-reload.

### Log File Location Configuration
**Pattern**: Optional custom log file path with home directory expansion
```python
# config.toml
[logging]
log_file = "~/my-logs/music-minion.log"  # Expands ~ to home directory

# config.py - Load and expand
log_file = logging_data.get('log_file')
if log_file:
    log_file = str(Path(log_file).expanduser())
```

**Learning**: Always use `Path.expanduser()` for user-provided paths. Default to `~/.local/share/music-minion/music-minion.log` if not specified.

---

**Last Updated**: 2025-11-20 after centralized logging implementation

## Loguru Migration (2025-11-21)

### Unified Logging with Loguru
**Pattern**: Single logging system with dual output for user-facing messages
```python
# core/output.py - Setup once at startup
from loguru import logger

def setup_loguru(log_file: Path, level: str = "INFO") -> None:
    """Configure loguru for file-only logging."""
    logger.remove()  # Remove default handler
    logger.add(
        log_file,
        rotation="10 MB",
        retention=5,
        level=level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{line} | {message}",
        enqueue=False,  # Synchronous for immediate writes
    )

def log(message: str, level: str = "info") -> None:
    """Unified logging: writes to file AND prints for blessed UI."""
    getattr(logger, level)(message)
    print(message)  # Blessed UI captures this
```

**Learning**: File-only logging with no console handler prevents conflicts with blessed terminal control. The `log()` helper provides dual output: file logging + UI display.

### Two Logging Patterns
**Background operations** (use loguru directly):
```python
from loguru import logger

# dev_reload.py, ipc/server.py, helpers.py
logger.error(f"Failed to reload {module_name}: {e}")
logger.warning("watchdog not installed - hot-reload unavailable")
logger.exception("Background sync failed")  # Auto-captures stack trace
```

**User-facing messages** (use log() helper):
```python
from music_minion.core.output import log

# commands/*.py - All command handlers
log(f"❌ Playlist '{name}' not found", level="error")
log(f"⚠️ No tracks available", level="warning")
log(f"✅ Created playlist: {name}", level="info")
```

**Learning**: Background operations use `logger` directly (file only). User-facing messages use `log()` helper (file + UI). This separation keeps concerns clear.

### Migration Statistics
- **10 files** migrated from stdlib logging to loguru (domain, commands, core)
- **284 print() statements** replaced with `log()` in command handlers
- **12 background print() statements** replaced with `logger` calls
- **23 verbose messages** marked with TODO for future cleanup
- **100 lines** of custom logging code eliminated

**Benefits**:
- ✅ Zero blessed UI conflicts (no stderr console handler)
- ✅ All user messages automatically logged to file
- ✅ Thread-safe with `enqueue=False` (synchronous writes)
- ✅ Automatic log rotation (10MB, 5 backups)
- ✅ Rich exception tracebacks with `logger.exception()`
- ✅ Single-line setup replaces 100-line custom module

---

**Last Updated**: 2025-11-21 after loguru migration
