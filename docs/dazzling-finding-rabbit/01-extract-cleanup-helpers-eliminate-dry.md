# Extract Cleanup Helpers to Eliminate DRY Violations

## Files to Modify
- `src/music_minion/helpers.py` (modify - add 2 new functions)
- `src/music_minion/main.py` (modify - replace 11 duplicated blocks)

## Implementation Details

### Problem
Web process cleanup duplicated 6x, file watcher cleanup duplicated 5x in main.py (total 11 duplicated code blocks)

### Solution
Add helper functions to `helpers.py` following existing patterns, then replace all duplicated blocks in `main.py`

### Step 1: Add Helper Functions to helpers.py

Add after line 398 (end of file):

```python
def cleanup_web_processes_safe(web_processes: tuple | None) -> None:
    """Safely stop web processes with isolated error handling.

    Args:
        web_processes: Tuple of (uvicorn_proc, vite_proc) or None
    """
    if not web_processes:
        return

    try:
        from . import web_launcher

        safe_print("\n🛑 Stopping web services...", style="yellow")
        web_launcher.stop_web_processes(*web_processes)
        logger.debug("Web processes stopped successfully")
    except Exception as e:
        # Log for debugging but don't raise - cleanup must complete
        logger.debug(f"Web process cleanup error (non-critical): {e}")


def cleanup_file_watcher_safe(observer) -> None:
    """Safely stop file watcher with isolated error handling.

    Args:
        observer: Watchdog Observer instance or None
    """
    if not observer:
        return

    try:
        from . import dev_reload

        dev_reload.stop_file_watcher(observer)
        logger.debug("File watcher stopped successfully")
    except Exception as e:
        logger.debug(f"File watcher cleanup error (non-critical): {e}")
```

### Step 2: Update Imports in main.py

Add import at top (after line 22, with other helpers import):

```python
from music_minion.helpers import (
    cleanup_web_processes_safe,
    cleanup_file_watcher_safe,
)
```

### Step 3: Replace 6 Web Process Cleanup Blocks in main.py

Replace these duplicated blocks with single function call `cleanup_web_processes_safe(web_processes)`:

- Lines 509-517
- Lines 597-605
- Lines 630-638
- Lines 683-691
- Lines 724-732
- Lines 760-768

Each block currently looks like:
```python
if web_processes:
    try:
        from . import web_launcher
        safe_print("\n🛑 Stopping web services...", style="yellow")
        web_launcher.stop_web_processes(*web_processes)
    except Exception:
        pass
```

Replace with:
```python
cleanup_web_processes_safe(web_processes)
```

### Step 4: Replace 5 File Watcher Cleanup Blocks in main.py

Replace these duplicated blocks with single function call `cleanup_file_watcher_safe(file_watcher_observer)`:

- Lines 606-614
- Lines 639-647
- Lines 692-700
- Lines 733-741
- Lines 769-777

Each block currently looks like:
```python
if file_watcher_observer:
    try:
        from . import dev_reload
        dev_reload.stop_file_watcher(file_watcher_observer)
    except Exception:
        pass
```

Replace with:
```python
cleanup_file_watcher_safe(file_watcher_observer)
```

## Acceptance Criteria

- [ ] 2 new helper functions added to `helpers.py`
- [ ] Import added to `main.py`
- [ ] All 11 duplicated blocks replaced with helper calls
- [ ] `ruff check src` passes with no new errors
- [ ] Run `music-minion --web`, verify graceful shutdown
- [ ] Check logs show no errors during cleanup
- [ ] Run `music-minion --dev`, verify file watcher cleanup works

## Dependencies
None - this is an independent refactoring task

## Verification Commands

```bash
# Verify no duplicate cleanup code remains
rg -A5 "web_launcher.stop_web_processes" src/music_minion/main.py | wc -l  # Should be 0

# Verify helper functions exist
rg "def cleanup_web_processes_safe" src/music_minion/helpers.py

# Run linter
uv run ruff check src/music_minion/helpers.py src/music_minion/main.py

# Test web mode
music-minion --web
# (then Ctrl-C to verify graceful shutdown)
```
