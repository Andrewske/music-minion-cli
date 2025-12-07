# Step 1: Fix Critical Issues in player.py

**Priority**: CRITICAL
**File**: `src/music_minion/domain/playback/player.py`
**Estimated Time**: 10 minutes

## Issues to Fix

### Issue 1: Dead Code Block (Lines 368-376)

**Severity**: Critical
**Location**: Lines 368-376 in `tick_session()` function

**Problem**:
There is unreachable dead code after the function return statement on line 366. This code is a duplicate `stop_playback` implementation that will never execute.

**Current Code**:
```python
def tick_session(state: PlayerState) -> PlayerState:
    """Tick the current listening session if playing.

    Should be called every second during playback.

    Args:
        state: Current player state

    Returns:
        Updated state (unchanged, but session is ticked)
    """
    if state.current_session_id is not None and state.is_playing:
        try:
            tick_listen_session(state.current_session_id, state.is_playing)
        except Exception as e:
            logger.warning(f"Failed to tick listening session: {e}")

    return state

    success = send_mpv_command(state.socket_path, {"command": ["stop"]})

    if success:
        return (
            state._replace(current_track=None, is_playing=False, playback_source=None),
            True,
        )

    return state, False
```

**Fix**: Delete lines 368-376 entirely (everything after the first `return state`).

**Expected Result**:
```python
def tick_session(state: PlayerState) -> PlayerState:
    """Tick the current listening session if playing.

    Should be called every second during playback.

    Args:
        state: Current player state

    Returns:
        Updated state (unchanged, but session is ticked)
    """
    if state.current_session_id is not None and state.is_playing:
        try:
            tick_listen_session(state.current_session_id, state.is_playing)
        except Exception as e:
            logger.warning(f"Failed to tick listening session: {e}")

    return state
```

---

### Issue 2: Poor Exception Handling (Line 266)

**Severity**: Critical
**Location**: Line 266 in `play_file()` function

**Problem**:
Exception handling uses `logger.warning()` which loses stack traces. Project standards (CLAUDE.md) require `logger.exception()` in except blocks for debugging.

**Current Code**:
```python
# Start new listening session if we have a track_id
session_id = None
if track_id is not None:
    try:
        session_id = start_listen_session(track_id, playlist_id)
    except Exception as e:
        logger.warning(f"Failed to start listening session: {e}")
```

**Fix**: Use `logger.exception()` with full context including track_id and playlist_id.

**Expected Result**:
```python
# Start new listening session if we have a track_id
session_id = None
if track_id is not None:
    try:
        session_id = start_listen_session(track_id, playlist_id)
    except Exception:
        logger.exception(
            f"Failed to start listening session: track_id={track_id}, playlist_id={playlist_id}"
        )
```

---

### Issue 3: Poor Exception Handling (Line 364)

**Severity**: Critical
**Location**: Line 364 in `tick_session()` function (will be ~line 355 after fixing Issue 1)

**Problem**:
Same issue as #2 - using `logger.warning()` instead of `logger.exception()`.

**Current Code**:
```python
if state.current_session_id is not None and state.is_playing:
    try:
        tick_listen_session(state.current_session_id, state.is_playing)
    except Exception as e:
        logger.warning(f"Failed to tick listening session: {e}")
```

**Fix**: Use `logger.exception()` with session_id context.

**Expected Result**:
```python
if state.current_session_id is not None and state.is_playing:
    try:
        tick_listen_session(state.current_session_id, state.is_playing)
    except Exception:
        logger.exception(
            f"Failed to tick listening session: session_id={state.current_session_id}"
        )
```

---

## Implementation Steps

1. **Delete dead code** (Issue 1):
   - Open `src/music_minion/domain/playback/player.py`
   - Navigate to the `tick_session()` function
   - Delete lines 368-376 (everything after the first `return state`)

2. **Fix exception in `play_file()`** (Issue 2):
   - Navigate to line ~266 in `play_file()` function
   - Replace `except Exception as e:` with `except Exception:`
   - Replace `logger.warning(f"Failed to start listening session: {e}")` with the new exception handler from above

3. **Fix exception in `tick_session()`** (Issue 3):
   - Navigate to the exception handler in `tick_session()` (should be around line 355 after previous fixes)
   - Replace `except Exception as e:` with `except Exception:`
   - Replace `logger.warning(...)` with the new exception handler from above

## Verification

After making changes, verify:
1. No unreachable code warnings from linters
2. All exception handlers in `player.py` use `logger.exception()` in except blocks
3. File compiles without syntax errors: `python -m py_compile src/music_minion/domain/playback/player.py`

## References

- Project CLAUDE.md: "Always use `logger.exception()` in except blocks (auto stack traces)"
- Project CLAUDE.md: "NEVER bare except - catch specific exceptions"
