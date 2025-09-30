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

**Last Updated**: 2025-09-29 after Phase 7 code review and bug fixes