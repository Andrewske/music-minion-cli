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

**Why suppression is safe:**
- Real errors are already caught and logged in `websocket_handler` exception blocks (lines 181-193)
- asyncio logger errors are just event loop complaining about exceptions we've already handled
- Suppressing prevents duplicate logging: asyncio stack trace + our logger.warning()
- Benign lifecycle events (refresh, HMR, tab close) shouldn't pollute UI or logs

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

        # CRITICAL: Suppress asyncio logger to prevent stderr output in blessed UI
        # Why suppression is safe:
        # 1. Real errors are caught/logged in websocket_handler (lines 181-193)
        # 2. asyncio logger just complains about exceptions we've already handled
        # 3. Prevents duplicate logging (asyncio stack trace + our logger.warning())
        # 4. Benign events (refresh, HMR, tab close) are normal lifecycle, not errors
        asyncio_logger = std_logging.getLogger("asyncio")
        asyncio_logger.setLevel(std_logging.CRITICAL)

        # Defense in depth: Add NullHandler to prevent lastResort stderr fallback
        if not asyncio_logger.handlers:
            asyncio_logger.addHandler(std_logging.NullHandler())

    except ImportError:
        logger.warning("websockets package not available, web control disabled")
        return
```

**Rationale:**
- **Line +3-4:** Add `silent_logging = True` following codebase pattern (used in `commands/library.py`, `commands/rating.py`)
- **Line +18-19:** Set asyncio logger to CRITICAL level to suppress WARNING/ERROR messages from event loop
- **Line +21-23:** Add NullHandler as defense-in-depth to ensure Python's lastResort handler is never invoked
- **Comments:** Document WHY suppression is safe (real errors already caught in exception handlers)
- **Logging standard:** Real WebSocket errors still logged via `logger.warning()` in exception handlers (server.py:189,193)

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
Verify real errors still logged to file via exception handlers:

**Test 1: Server startup logged**
```bash
tail -20 ~/.local/share/music-minion/logs/music-minion.log | grep "WebSocket server started"
```
Expected: `WebSocket server started on ws://localhost:8765`

**Test 2: Real errors still logged (not suppressed)**
Simulate a real error by breaking the WebSocket connection abnormally:
1. Start `music-minion --web`
2. Open browser DevTools → Network tab
3. Connect to web frontend
4. Forcibly terminate the connection (close tab mid-request or kill browser process)
5. Check log file:
```bash
tail -50 ~/.local/share/music-minion/logs/music-minion.log | grep -i "websocket"
```

Expected:
- Benign errors (handshake, refresh, HMR): NOT logged (suppressed by asyncio logger config)
- Real errors (OSError, unexpected exceptions): LOGGED via `logger.warning()` in exception handlers
- Example: `WebSocket OSError: [Errno 104] Connection reset by peer` (if applicable)

**Test 3: Exception handler logging intact**
Verify exception handlers at server.py:181-193 are still functioning:
```bash
# Should see logger.warning() calls for real errors, not asyncio stack traces
grep -A2 "WebSocket.*error" ~/.local/share/music-minion/logs/music-minion.log
```

### Visual Test
**Before fix:** Stack traces with lines like:
```
opening handshake failed
Traceback (most recent call last):
  File "/home/kevin/.venv/lib/python3.12/site-packages/websockets/http11.py", line 138, in parse
EOFError: stream ends after 0 bytes, before end of line
```

**After fix:** Clean blessed UI with no stack traces

## Logging Standard Compliance

This implementation follows the Music Minion logging standard:

**Background threads (WebSocket server):**
- ✅ `silent_logging = True` prevents loguru output in blessed UI
- ✅ `logger.warning()` in exception handlers logs real errors to file

**Suppression strategy:**
- ✅ asyncio logger suppressed to prevent duplicate logging
- ✅ Real errors still logged via exception handlers (not lost)
- ✅ Benign lifecycle events (refresh, HMR, close) neither in UI nor logs
- ✅ Dual output pattern: User sees clean UI, devs see actionable errors in log file

**Why this isn't a logging standard violation:**
- asyncio logger errors are just event loop complaining about exceptions we've already handled
- Exception handlers (server.py:181-193) provide better context than asyncio stack traces
- No data loss: Real errors logged via `logger.warning()`, benign events suppressed

## Dependencies
None - This is an independent fix for the logging system.

## Related Files (No Changes)
- `src/music_minion/core/output.py` - Logging system reference (silent_logging pattern)
- `src/music_minion/ipc/server.py:181-193` - Exception handlers that log real WebSocket errors
- `src/music_minion/commands/library.py` - Example of silent_logging usage (line 71, 157)

## Rollback Plan
If issues arise:
1. Remove asyncio_logger configuration (lines ~18-23)
2. Remove silent_logging = True (lines ~3-4)
3. Original code is simple to restore as changes are additive
