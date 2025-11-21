# Loguru Migration Plan

**Created**: 2025-11-20
**Status**: Ready for implementation
**Estimated effort**: 8-10 hours

## Overview

Migrate Music Minion CLI from stdlib `logging` to `loguru` for unified dual output (console + file). This enables every message shown to users to also be logged to file, improving debugging and production support.

### Current State
- Using stdlib `logging` with `RotatingFileHandler`
- 10 files use `logging.getLogger(__name__)`
- ~700 `print()` statements in command handlers
- Background operations print to stderr (not logged)
- Custom `core/logging.py` setup (~100 lines)

### Target State
- Single `loguru` package for all logging
- All user-facing messages also logged to file
- Exception stack traces automatically logged
- Simple 3-line setup replaces custom logging module
- Background operations use logger instead of print

---

## Why Loguru?

1. **Built-in dual output**: Logs to file AND prints to console automatically
2. **Simpler code**: 100 lines of custom setup → 3 lines of loguru config
3. **Better exceptions**: Rich stack traces with context
4. **Auto-rotation**: Built-in log rotation (10MB, 5 backups)
5. **Thread-safe**: Enqueue mode for background operations
6. **Production-ready**: 18k+ GitHub stars, widely used

---

## Implementation Plan

### Phase 1: Setup Loguru (1 hour)

#### 1.1 Add Dependency

**File**: `pyproject.toml`

```toml
dependencies = [
    "loguru>=0.7.0",
    # ... existing dependencies
]
```

**Run**: `uv pip install loguru`

#### 1.2 Create Output Module

**Create file**: `src/music_minion/core/output.py`

```python
"""
Unified output system using Loguru.
Replaces print() statements and stdlib logging with dual output (console + file).
"""

import sys
from pathlib import Path
from loguru import logger

def setup_loguru(log_file: Path, level: str = "INFO", console_level: str = "INFO"):
    """
    Configure loguru for dual output: console (stderr) + file.

    Args:
        log_file: Path to log file
        level: Minimum level for file logging (DEBUG, INFO, WARNING, ERROR)
        console_level: Minimum level for console output (typically INFO)
    """
    # Remove default handler
    logger.remove()

    # Console output (stderr) - shown to user in blessed UI
    logger.add(
        sys.stderr,
        level=console_level,
        format="<level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{line}</cyan> | {message}",
        colorize=True,
    )

    # File output - detailed logging with rotation
    logger.add(
        log_file,
        rotation="10 MB",
        retention=5,  # Keep 5 backup files
        level=level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{line} | {message}",
        enqueue=True,  # Thread-safe
    )

    logger.info(f"Loguru initialized: {log_file} (console={console_level}, file={level})")
```

#### 1.3 Update Entry Points

**File**: `src/music_minion/cli.py`

Replace existing logging setup (around lines 20-30):

```python
# OLD
from music_minion.core.logging import setup_logging
setup_logging(cfg)

# NEW
from music_minion.core.output import setup_loguru
from pathlib import Path

log_file = Path.home() / ".local/share/music-minion/music-minion.log"
log_file.parent.mkdir(parents=True, exist_ok=True)
setup_loguru(log_file, level="DEBUG", console_level="INFO")
```

**File**: `src/music_minion/main.py`

Same replacement in `main()` function (around line 515)

#### 1.4 Test Basic Setup

```bash
uv run music-minion
# Should see loguru initialization message
# Verify log file created at ~/.local/share/music-minion/music-minion.log
```

---

### Phase 2: Migrate Existing Logger Usage (2 hours)

Replace stdlib logging imports with loguru in 10 files.

#### Migration Pattern

```python
# OLD
import logging
logger = logging.getLogger(__name__)

# NEW
from loguru import logger
```

#### Files to Migrate

**1. `src/music_minion/domain/playback/player.py`**
- Lines: 1 (import), 53, 92, 129, 135, 170
- ~6 logger calls: `logger.info()`, `logger.error()`
- Update import at top of file
- No other changes needed (API compatible)

**2. `src/music_minion/domain/playlists/crud.py`**
- Lines: 1 (import), 427, 467, 470, 472, 475, 482, etc.
- ~15 logger calls: `logger.info()`, `logger.warning()`, `logger.error()`
- Update import at top of file

**3. `src/music_minion/domain/playlists/sync.py`**
- Line 1 (import), 261 (exception logging)
- ~5 logger calls: `logger.error()`, `logger.exception()`
- Update import at top of file

**4. `src/music_minion/commands/rating.py`**
- Lines: 1 (import), usage throughout
- ~3 logger calls: `logger.info()`, `logger.warning()`
- Update import at top of file

**5. `src/music_minion/commands/track.py`**
- Lines: 1 (import), 29, 74, 102
- ~4 logger calls: `logger.info()`, `logger.error()`
- Update import at top of file

**6. `src/music_minion/core/database.py`**
- Lines: 1 (import), 596, etc.
- ~3 logger calls: `logger.info()`
- Update import at top of file

**7. `src/music_minion/domain/library/scanner.py`**
- Lines: 1 (import)
- ~2 logger calls: `logger.info()`, `logger.warning()`
- Update import at top of file

**8. `src/music_minion/domain/library/providers/soundcloud/api.py`**
- Lines: 1 (import)
- ~2 logger calls: `logger.info()`, `logger.error()`
- Update import at top of file

**9. `src/music_minion/domain/ai/review.py`**
- Lines: 1 (import)
- ~2 logger calls: `logger.info()`
- Update import at top of file

**10. `src/music_minion/domain/playlists/exporters.py`**
- Lines: 1 (import)
- ~1 logger call: `logger.info()`
- Update import at top of file

#### Testing After Each File
```bash
# Import the module in Python to check for errors
python -c "from music_minion.domain.playback import player"

# Run app to verify runtime behavior
uv run music-minion
```

---

### Phase 3: Replace Background print() Statements (1 hour)

Background operations should use logger, not print (these don't need user display).

#### 3.1 `dev_reload.py`

```python
# Add at top:
from loguru import logger

# Line 144
# OLD: print(f"❌ Failed to reload {module_name}: {e}")
# NEW:
logger.error(f"Failed to reload {module_name}: {e}")

# Lines 161-162
# OLD:
#   print("⚠️  watchdog not installed - hot-reload unavailable")
#   print("   Install with: uv pip install watchdog")
# NEW:
logger.warning("watchdog not installed - hot-reload unavailable")
logger.info("Install with: uv pip install watchdog")

# Line 180
# OLD: print(f"⚠️  Failed to setup file watcher: {e}")
# NEW:
logger.warning(f"Failed to setup file watcher: {e}")
```

#### 3.2 `ipc/server.py`

```python
# Add at top:
from loguru import logger

# Line 114
# OLD: print(f"Error accepting connection: {e}")
# NEW:
logger.error(f"Error accepting connection: {e}")

# Line 117
# OLD: print(f"IPC server error: {e}")
# NEW:
logger.exception(f"IPC server error")  # Gets stack trace automatically
```

#### 3.3 `ui/blessed/app.py`

```python
# Add at top:
from loguru import logger

# Line 297
# OLD: print(f"Warning: Error polling player state: {e}", file=sys.stderr)
# NEW:
logger.warning(f"Error polling player state: {e}")

# Line 300
# OLD: print(f"Unexpected error polling player state: {type(e).__name__}: {e}", file=sys.stderr)
# NEW:
logger.error(f"Unexpected error polling: {type(e).__name__}: {e}")
```

#### 3.4 `helpers.py`

```python
# Add at top:
from loguru import logger

# Line 213 (auto-export warning)
# OLD: print("Warning: Cannot auto-export - no library paths configured", file=sys.stderr)
# NEW:
logger.warning("Cannot auto-export - no library paths configured")

# Line 229 (auto-export error)
# OLD: print(f"Auto-export failed: {e}", file=sys.stderr)
# NEW:
logger.exception("Auto-export failed")  # Stack trace included

# Line 232 (unexpected error)
# OLD: print(f"Unexpected error during auto-export: {e}", file=sys.stderr)
# NEW:
logger.exception("Unexpected error during auto-export")

# Line 64 (background sync)
# OLD: print(f"⚠️  Background sync failed: {e}")
# NEW:
logger.exception("Background sync failed")
```

---

### Phase 4: Add Logging to Command Handlers (3 hours)

**Strategy**: Keep `print()` for user-facing output, ADD `logger` calls for debugging.

#### Pattern for Exception Handlers

```python
# BEFORE
try:
    # ... operation ...
except Exception as e:
    print(f"❌ Sync failed: {e}")

# AFTER
from loguru import logger

try:
    # ... operation ...
except Exception as e:
    logger.exception(f"Sync failed for {provider}")  # Detailed log with stack trace
    print(f"❌ Sync failed: {e}")  # User-friendly message
```

#### Pattern for Validation Errors

```python
# BEFORE
if not playlist:
    print(f"❌ Playlist '{name}' not found")
    return ctx, True

# AFTER
from loguru import logger

if not playlist:
    logger.error(f"Playlist '{name}' not found in {active_library} library")
    print(f"❌ Playlist '{name}' not found")
    return ctx, True
```

#### Pattern for Warnings

```python
# BEFORE
if not tracks:
    print("⚠️  No tracks found")

# AFTER
from loguru import logger

if not tracks:
    logger.warning("No tracks found - library may be empty")
    print("⚠️  No tracks found")
```

#### Files and Lines to Update

**4.1 `commands/library.py`**

Add `from loguru import logger` at top.

- Line 452: Add `logger.exception(f"Sync failed for {provider_name}")` before print
- Lines with errors: Add `logger.error()` before user-facing print
- Lines with warnings: Add `logger.warning()` before user-facing print

**4.2 `commands/playlist.py`** (~200 print statements)

Add `from loguru import logger` at top.

Exception handlers to update:
- Line 222: `logger.exception("Error evaluating filters")`
- Line 294: `logger.exception("AI parsing error")`
- Line 352: `logger.error(f"Playlist creation failed: {e}")`
- Line 366: `logger.exception("Error adding filters to playlist")`
- Line 415: `logger.exception("Error evaluating AI filters")`
- Line 506: `logger.exception(f"Error creating playlist: {e}")`
- Line 555: `logger.exception(f"Error deleting playlist: {e}")`
- Line 591: `logger.exception(f"Error renaming playlist: {e}")`
- Line 776: `logger.exception(f"Error setting active playlist: {e}")`
- Line 848: `logger.exception(f"Error importing playlist: {e}")`
- Line 942: `logger.exception(f"Error exporting playlist: {e}")`
- Line 1031: `logger.exception(f"Error analyzing playlist: {e}")`

Validation errors to log:
- Line 534: `logger.error(f"Playlist '{name}' not found")`
- Line 581: `logger.error(f"Playlist '{old_name}' not found")`
- Line 611: `logger.error(f"Playlist '{name}' not found")`
- Line 654: `logger.error(f"Playlist '{name}' not found")`

**4.3 `commands/track.py`**

Add `from loguru import logger` at top.

- Line 99: `logger.exception(f"Error adding track to playlist: {e}")`
- Line 103: `logger.exception(f"Error adding track to playlist: {e}")`
- Line 187: `logger.exception(f"Error removing track from playlist: {e}")`
- Line 191: `logger.exception(f"Error removing track from playlist: {e}")`

**4.4 `commands/playback.py`**

Add `from loguru import logger` at top.

- Line 152: `logger.error("Failed to start MPV player")`
- Line 187: `logger.error("Failed to play track")`

**4.5 `commands/rating.py`**

Already has logger import. Add to exception handlers:

- Lines 152-153: `logger.exception("SoundCloud sync error")`
- Lines 380-381: `logger.exception("SoundCloud unlike error")`

**4.6 `commands/admin.py`**

Add `from loguru import logger` at top.

- Line 218: `logger.exception(f"Error killing MPV: {e}")`
- Line 261: `logger.exception(f"Error getting statistics: {e}")`
- Line 328: `logger.exception(f"Error scanning library: {e}")`

**4.7 `router.py`**

Add `from loguru import logger` at top.

Add logging for unknown commands:
- Line 312: `logger.warning(f"Unknown command: '{command}'")`

---

### Phase 5: Cleanup (1 hour)

#### 5.1 Delete Old Logging Module

**Delete file**: `src/music_minion/core/logging.py`

This 100-line module is no longer needed.

#### 5.2 Verify No Old Imports

```bash
# Check for any remaining imports of old logging module
grep -r "from music_minion.core.logging import" src/
grep -r "from music_minion.core import logging" src/

# Should return no results
```

#### 5.3 Clean Up safe_print (Optional)

**Current locations**:
- `helpers.py:20`
- `main.py:43`
- `commands/playback.py:18`
- `commands/library.py:17`

**Option A**: Keep for now (they still work with executor.py capture)

**Option B**: Enhance to also log:
```python
from loguru import logger

def safe_print(ctx: AppContext, message: str, style: Optional[str] = None) -> None:
    """Print with console styling AND log to file."""
    # Auto-detect log level from message
    if "❌" in message or "error" in message.lower():
        logger.error(message)
    elif "⚠️" in message or "warning" in message.lower():
        logger.warning(message)
    else:
        logger.info(message)

    # Display to user
    if ctx.console:
        if style:
            ctx.console.print(message, style=style)
        else:
            ctx.console.print(message)
    else:
        print(message)
```

**Recommendation**: Option A for now (gradual migration)

---

### Phase 6: Testing (1 hour)

#### 6.1 Verify Dual Output

```bash
# Terminal 1: Run app
uv run music-minion

# Terminal 2: Tail log file
tail -f ~/.local/share/music-minion/music-minion.log

# Test:
# 1. Run commands in blessed UI
# 2. Verify messages appear in BOTH command history AND log file
# 3. Check timestamps and formatting
```

#### 6.2 Test Exception Logging

```bash
# Trigger error conditions:
# - Try to sync without authentication
# - Try to play non-existent track
# - Try to import invalid playlist file

# Verify:
# - User sees friendly error in command history
# - Log file contains full stack trace
# - Exception details preserved
```

#### 6.3 Test Log Rotation

```bash
# Check log files
ls -lh ~/.local/share/music-minion/

# Should see:
# music-minion.log (current)
# music-minion.log.1 (first backup)
# etc. up to .5

# Force rotation by creating large log:
# (if needed for testing)
python -c "
from loguru import logger
from pathlib import Path
logger.add(Path.home() / '.local/share/music-minion/music-minion.log', rotation='1 MB')
for i in range(100000):
    logger.info(f'Test message {i}')
"
```

#### 6.4 Test Thread Safety

```bash
# Run app with background operations
uv run music-minion

# Enable auto-sync, hot-reload, etc.
# Monitor log file for interleaved/corrupted messages
# Should be clean due to enqueue=True
```

#### 6.5 Regression Testing

Test all major features:
- [ ] Playback (play, pause, skip)
- [ ] Rating (like, love, archive)
- [ ] Playlists (create, show, active)
- [ ] Library sync (soundcloud)
- [ ] Command history shows messages
- [ ] Log file captures everything

---

### Phase 7: Documentation (30 minutes)

#### 7.1 Update `CLAUDE.md`

Replace "Logging Strategy" section:

```markdown
### Logging Strategy
**CRITICAL**: Always use loguru for logging - never use print() for debugging or error messages.

- **Centralized logging**: Configured once at startup via `core/output.py`
- **Dual output**: All logs go to both console (stderr) and file
- **Default location**: `~/.local/share/music-minion/music-minion.log`
- **Automatic rotation**: 10MB max file size, 5 backups
- **Format (console)**: `LEVEL | module:line | message` (colorized)
- **Format (file)**: `2025-11-20 15:12:11 | LEVEL | module:line | message`
- **Thread-safe**: Background operations safely log with enqueue=True

**Usage Pattern** (REQUIRED):
```python
# At top of every module
from loguru import logger

# In your code - use logger, not print()
logger.debug("Detailed information for diagnosing problems")
logger.info("General informational messages")
logger.warning("Warning messages for unexpected but handled situations")
logger.error("Error messages for serious problems")
logger.exception("Error with full stack trace - use in except blocks")
```

**Benefits**:
- ✅ All logs automatically saved to file (survives app restarts)
- ✅ Zero per-module configuration needed
- ✅ Automatic log rotation prevents disk overflow
- ✅ Module and line number automatically included
- ✅ Colorized console output for better readability
- ✅ Thread-safe for background operations
- ✅ Rich exception tracebacks with context
```

#### 7.2 Update `ai-learnings.md`

Add section on loguru patterns:

```markdown
## Loguru Logging Patterns

### Basic Usage
```python
from loguru import logger

# Info, warnings, errors
logger.info("Library sync completed: 150 tracks added")
logger.warning("No tracks found - library may be empty")
logger.error("Authentication failed")

# Exception logging (automatic stack trace)
try:
    sync_library(provider)
except Exception as e:
    logger.exception(f"Sync failed for {provider}")  # Full traceback in log
    print(f"❌ Sync failed: {e}")  # User-friendly message
```

### Dual Output Pattern

User-facing commands:
- **logger.exception()** → Detailed error with stack trace in log file
- **print()** → User-friendly message in command history

Background operations:
- **logger.error()** → Error goes to log file only
- No print() needed (not user-facing)

### Thread Safety

Background threads automatically use thread-safe logging (enqueue=True):
```python
def background_task():
    try:
        # Safe to log from background thread
        logger.info("Background operation started")
        # ... work ...
        logger.info("Background operation completed")
    except Exception as e:
        logger.exception("Background operation failed")
```
```

---

## Migration Checklist

### Phase 1: Setup
- [ ] Add `loguru>=0.7.0` to `pyproject.toml`
- [ ] Run `uv pip install loguru`
- [ ] Create `src/music_minion/core/output.py`
- [ ] Update `src/music_minion/cli.py` entry point
- [ ] Update `src/music_minion/main.py` entry point
- [ ] Test: Verify loguru initializes and creates log file

### Phase 2: Migrate Existing Logger Usage
- [ ] `domain/playback/player.py`
- [ ] `domain/playlists/crud.py`
- [ ] `domain/playlists/sync.py`
- [ ] `commands/rating.py`
- [ ] `commands/track.py`
- [ ] `core/database.py`
- [ ] `domain/library/scanner.py`
- [ ] `domain/library/providers/soundcloud/api.py`
- [ ] `domain/ai/review.py`
- [ ] `domain/playlists/exporters.py`
- [ ] Test: Import each module, run basic commands

### Phase 3: Replace Background print()
- [ ] `dev_reload.py` (7 statements)
- [ ] `ipc/server.py` (2 statements)
- [ ] `ui/blessed/app.py` (3 statements)
- [ ] `helpers.py` (5 statements)
- [ ] Test: Verify background operations log correctly

### Phase 4: Add Logging to Command Handlers
- [ ] `commands/library.py` (~10 error handlers)
- [ ] `commands/playlist.py` (~15 error handlers)
- [ ] `commands/track.py` (~5 error handlers)
- [ ] `commands/playback.py` (~5 error handlers)
- [ ] `commands/rating.py` (~5 error handlers)
- [ ] `commands/admin.py` (~5 error handlers)
- [ ] `router.py` (unknown command logging)
- [ ] Test: Trigger errors, verify dual output

### Phase 5: Cleanup
- [ ] Delete `core/logging.py`
- [ ] Verify no old logging imports remain
- [ ] (Optional) Enhance safe_print to log
- [ ] Test: Full regression test suite

### Phase 6: Testing
- [ ] Dual output (console + file)
- [ ] Exception logging (stack traces)
- [ ] Log rotation (10MB, 5 backups)
- [ ] Thread safety (background operations)
- [ ] Regression (all features work)

### Phase 7: Documentation
- [ ] Update `CLAUDE.md` logging section
- [ ] Update `ai-learnings.md` with patterns
- [ ] Create this migration plan document ✅

---

## Rollback Plan

### Quick Rollback (if critical issues)
```bash
# Revert to previous commit
git revert <commit-hash>

# Or reset to before migration
git reset --hard <commit-before-migration>
```

### Partial Rollback (keep progress)
```bash
# Restore old logging module temporarily
git checkout <commit-before-migration> -- src/music_minion/core/logging.py

# Allow both systems to coexist:
# - New code uses loguru
# - Old code still works with restored logging.py
# - Gradual migration continues
```

### Compatibility Bridge (emergency)

If needed, create bridge to support both:

```python
# core/output.py - add this for compatibility
import logging
from loguru import logger

class LoguruHandler(logging.Handler):
    """Bridge handler: stdlib logging → loguru"""

    def emit(self, record):
        # Get corresponding loguru level
        level = record.levelname
        if level == "DEBUG":
            logger.debug(record.getMessage())
        elif level == "INFO":
            logger.info(record.getMessage())
        elif level == "WARNING":
            logger.warning(record.getMessage())
        elif level == "ERROR":
            logger.error(record.getMessage())
        elif level == "CRITICAL":
            logger.critical(record.getMessage())

# Add to stdlib logging root logger
logging.root.addHandler(LoguruHandler())
```

---

## Success Criteria

✅ **All modules use loguru** instead of stdlib logging
✅ **Dual output works** (console + file) for all messages
✅ **Exception stack traces** appear in log file
✅ **Log rotation functional** (10MB files, 5 backups)
✅ **No print() in background operations** (use logger instead)
✅ **Thread-safe logging** verified for background tasks
✅ **Documentation updated** (CLAUDE.md, ai-learnings.md)
✅ **All tests passing** (no regression)
✅ **User experience unchanged** (messages still appear in command history)
✅ **Log file useful** for debugging production issues

---

## Timeline Estimate

- **Phase 1** (Setup): 1 hour
- **Phase 2** (Migrate logger usage): 2 hours
- **Phase 3** (Background print): 1 hour
- **Phase 4** (Command handlers): 3 hours
- **Phase 5** (Cleanup): 1 hour
- **Phase 6** (Testing): 1 hour
- **Phase 7** (Documentation): 30 minutes

**Total**: ~8-10 hours for complete migration

Can be done incrementally:
- Week 1: Phases 1-3 (foundation + background operations)
- Week 2: Phase 4 (command handlers)
- Week 3: Phases 5-7 (cleanup, testing, docs)

---

## References

- **Loguru Documentation**: https://loguru.readthedocs.io/
- **GitHub**: https://github.com/Delgan/loguru
- **Migration Guide**: https://loguru.readthedocs.io/en/stable/resources/migration.html
- **Best Practices**: https://loguru.readthedocs.io/en/stable/resources/recipes.html

---

**Last Updated**: 2025-11-20
**Status**: Ready for implementation
