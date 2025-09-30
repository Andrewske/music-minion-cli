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

### Test Files
- Adhoc test scripts in project root (e.g., `test_sync_fixes.py`)
- Delete after testing or keep for regression

### Documentation
- **Main Plan**: `docs/playlist-system-plan.md` - Implementation plan with phases, learnings
- **Project Guide**: `CLAUDE.md` - Development guidelines for AI assistants
- **Global Prefs**: `~/.claude/CLAUDE.md` - User's global development preferences

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

**Pattern**: Always use atomic writes for user data
```python
temp_path = file_path + '.tmp'
try:
    audio.save(temp_path)
    os.replace(temp_path, file_path)  # Atomic
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

**Solution**: Atomic writes (temp file + rename)
```python
temp_path = file_path + '.tmp'
audio.save(temp_path)
os.replace(temp_path, file_path)  # Atomic
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

**CRITICAL**: File operations modifying user data MUST be atomic.

**Pattern**:
```python
temp_path = file_path + '.tmp'
try:
    audio.save(temp_path)
    os.replace(temp_path, file_path)  # Atomic on Unix/Windows
except Exception:
    if os.path.exists(temp_path):
        os.remove(temp_path)
    raise
```

**Why**: Crashes during write corrupt metadata permanently. No recovery possible without atomic writes.

**Learning**: `os.replace()` is atomic on both Unix and Windows. Use temp file + rename pattern for all writes.

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

**Last Updated**: 2025-09-29 after extracting learnings from playlist-system-plan.md