# Suppress WebSocket Errors in Blessed UI

## Problem
WebSocket handshake error stack traces appear in the blessed UI terminal instead of being logged to file. Errors are benign (browser refresh, Vite HMR, tab close) but visually disruptive.

## Files to Modify
- `src/music_minion/ipc/server.py` (modify)

## Root Cause
- Only `websockets` logger suppressed, not `asyncio` logger (lines 156-157)
- asyncio event loop errors → asyncio logger → Python lastResort handler → stderr → blessed terminal
- WebSocket thread doesn't use `silent_logging=True` pattern
- No NullHandler to prevent lastResort fallback

**Error flow:**
```
asyncio event loop exception
  → asyncio logger (WARNING/ERROR level)
  → root logger (no handlers configured)
  → Python's lastResort handler
  → sys.stderr
  → blessed terminal (bypasses UI)
```

## Implementation Details

### Step 1: Suppress asyncio logger and add silent_logging
**Location:** Lines 148-160 (replace _run_websocket_server start)

```python
def _run_websocket_server(self) -> None:
    """Run the WebSocket server for web frontend connections."""
    import threading

    # Mark thread as silent to prevent loguru output in blessed UI
    threading.current_thread().silent_logging = True

    try:
        import websockets  # type: ignore[import]
        import logging as std_logging

        # Suppress benign handshake/connection error logs
        websockets_logger = std_logging.getLogger("websockets")
        websockets_logger.setLevel(std_logging.ERROR)

        # CRITICAL: Suppress asyncio logger to prevent errors in blessed UI
        # asyncio event loop logs to asyncio logger → root → lastResort → stderr
        asyncio_logger = std_logging.getLogger("asyncio")
        asyncio_logger.setLevel(std_logging.CRITICAL)

        # Defense in depth: Add NullHandler to prevent lastResort fallback
        if not asyncio_logger.handlers:
            asyncio_logger.addHandler(std_logging.NullHandler())

    except ImportError:
        logger.warning("websockets package not available, web control disabled")
        return
```

**Rationale:**
- **Line +3-4:** Add `silent_logging = True` following codebase pattern (used in `commands/library.py`, `commands/rating.py`)
- **Line +18-19:** Set asyncio logger to CRITICAL level to suppress WARNING/ERROR messages
- **Line +21-23:** Add NullHandler as defense-in-depth to ensure Python's lastResort handler is never invoked
- **Comments:** Explain WHY this is needed (prevents stderr bypass of blessed UI)

## Acceptance Criteria

### Functional Tests
1. ✓ Start `music-minion --web`
2. ✓ Browser refresh (F5) repeatedly - NO errors in blessed UI
3. ✓ Vite HMR (edit frontend file) - NO connection errors in UI
4. ✓ Close browser tab - NO "connection closed" errors in UI
5. ✓ WebSocket server continues functioning normally
6. ✓ IPC commands still work (Unix socket unaffected)
7. ✓ Web frontend can connect and send commands
8. ✓ Blessed UI remains responsive and clean

### Logging Verification
Verify errors still logged to file for debugging:
```bash
tail ~/.local/share/music-minion/logs/music-minion.log | grep "WebSocket server started"
```

Expected:
- Server startup logged: "WebSocket server started on ws://localhost:8765"
- File logging unaffected by stderr suppression
- WebSocket errors (if any) still in log file, just not in terminal

### Visual Test
**Before fix:** Stack traces with lines like:
```
opening handshake failed
Traceback (most recent call last):
  File "/home/kevin/.venv/lib/python3.12/site-packages/websockets/http11.py", line 138, in parse
EOFError: stream ends after 0 bytes, before end of line
```

**After fix:** Clean blessed UI with no stack traces

## Dependencies
None - This is an independent fix for the logging system.

## Related Files (No Changes)
- `src/music_minion/core/output.py` - Logging system reference (silent_logging pattern)
- `src/music_minion/ui/blessed/events/commands/executor.py` - Reference for redirect_stderr pattern
- `src/music_minion/commands/library.py` - Example of silent_logging usage (line 71, 157)

## Rollback Plan
If issues arise:
1. Remove asyncio_logger configuration (lines ~18-23)
2. Remove silent_logging = True (lines ~3-4)
3. Original code is simple to restore as changes are additive
