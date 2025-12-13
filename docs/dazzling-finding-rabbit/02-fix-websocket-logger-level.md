# Revert WebSocket Logger Level to ERROR

## Files to Modify
- `src/music_minion/ipc/server.py` (modify - line 161 and comment)

## Implementation Details

### Problem
Line 161 sets `websockets_logger.setLevel(std_logging.CRITICAL)`, which suppresses ERROR-level logs that could indicate real problems.

### Solution
Revert to ERROR level while keeping asyncio suppression. Exception handling in `websocket_handler()` (lines 200-212) already suppresses benign errors.

### Changes to server.py

**Line 161** - Change log level:
```python
# Before:
websockets_logger.setLevel(std_logging.CRITICAL)

# After:
websockets_logger.setLevel(std_logging.ERROR)
```

**Lines 159-161** - Update comment:
```python
# Suppress benign handshake/connection error logs
# Set to ERROR to suppress DEBUG/INFO noise while preserving real error visibility
websockets_logger.setLevel(std_logging.ERROR)
```

### Rationale
ERROR-level logs are valuable for debugging real issues. The exception handling in `websocket_handler()` already suppresses benign errors (ConnectionClosed, InvalidHandshake, OSError), so we don't lose protection against noise while gaining visibility into real problems.

## Acceptance Criteria

- [ ] `websockets_logger` set to ERROR level (not CRITICAL)
- [ ] Comment updated to explain reasoning
- [ ] `ruff check src` passes
- [ ] Run `music-minion --web`, start browser frontend
- [ ] Trigger intentional WebSocket error (e.g., send corrupt JSON via browser DevTools)
- [ ] Verify ERROR-level logs appear in `~/.local/share/music-minion/logs/music-minion.log`
- [ ] Verify benign handshake errors (refresh, HMR) still suppressed

## Dependencies
None - this is an independent fix

## Verification Commands

```bash
# Verify logger level change
rg "websockets_logger.setLevel" src/music_minion/ipc/server.py

# Run linter
uv run ruff check src/music_minion/ipc/server.py

# Test WebSocket server
music-minion --web
# Then test in browser DevTools console:
# ws = new WebSocket('ws://localhost:8765');
# ws.onopen = () => ws.send('invalid json');

# Check log file for ERROR-level logs
tail -50 ~/.local/share/music-minion/logs/music-minion.log | grep -i websocket
```
