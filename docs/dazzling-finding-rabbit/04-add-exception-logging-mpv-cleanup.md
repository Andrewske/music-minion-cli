# Add Specific Exception Logging to MPV Cleanup

## Files to Modify
- `src/music_minion/domain/playback/player.py` (modify - lines 127-131)

## Implementation Details

### Problem
Lines 127-131 use bare `except Exception: pass` which suppresses ALL exceptions including unexpected ones, making debugging impossible.

### Solution
Add specific exception handling for expected errors (OSError, TimeoutExpired) while logging unexpected exceptions.

### Changes to player.py

**Lines 127-131** - Replace bare exception handler:

```python
# Before:
try:
    state.process.kill()
    state.process.wait(timeout=2.0)
except Exception:
    pass

# After:
try:
    state.process.kill()
    state.process.wait(timeout=2.0)
except (OSError, subprocess.TimeoutExpired):
    pass  # Process already terminated or couldn't be killed
except Exception as e:
    logger.warning(f"Unexpected error during MPV cleanup: {e}")
```

### Rationale
- **OSError**: Expected when process is already dead
- **TimeoutExpired**: Expected if process takes longer than 2s to terminate
- **Other exceptions**: These are bugs and should be logged for investigation

### Note
The `main.py` cleanup logging is already handled by Task #1 (cleanup helper functions include `logger.debug()` calls).

## Acceptance Criteria

- [ ] Specific exception types caught explicitly (OSError, TimeoutExpired)
- [ ] Unexpected exceptions logged with `logger.warning()`
- [ ] `ruff check src` passes
- [ ] Manually test MPV cleanup: `music-minion` → play track → quit
- [ ] Check log file for any "Unexpected error" messages (should be none in normal operation)
- [ ] Verify graceful shutdown even if MPV process is externally killed

## Dependencies
None - independent change

## Verification Commands

```bash
# Verify changes applied
rg -A5 "def stop_mpv" src/music_minion/domain/playback/player.py

# Run linter
uv run ruff check src/music_minion/domain/playback/player.py

# Test MPV cleanup
music-minion
# Play a track, then quit
# Check log file:
tail -50 ~/.local/share/music-minion/logs/music-minion.log | grep -i "mpv cleanup"

# Test external kill (advanced)
# 1. Start music-minion, play track
# 2. In another terminal: pkill -9 mpv
# 3. Quit music-minion
# 4. Verify log shows clean shutdown (no unexpected errors)
```
