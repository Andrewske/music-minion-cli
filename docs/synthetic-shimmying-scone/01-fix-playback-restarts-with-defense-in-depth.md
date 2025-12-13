# Fix Playback Restarts with Defense-in-Depth

## Problem
Songs restart after 1-2 seconds due to incomplete metadata loading. Duration polling timeout (500ms) is too short for network streams/slow metadata parsing, causing `is_track_finished()` to see incomplete duration and trigger false autoplay.

## Files to Modify
- `src/music_minion/domain/playback/player.py` (modify)

## Root Cause
- Duration polling exits early with incomplete duration (e.g., 2.0s instead of 180.0s)
- `is_track_finished()` check: `position >= duration - 0.5` triggers immediately
- No validation for suspiciously short durations or minimum playback time

## Implementation Details

### Step 1: Add playback_started_at to PlayerState
**Location:** Lines 21-32 (PlayerState class)

Add new field to track when playback started:
```python
class PlayerState(NamedTuple):
    socket_path: Optional[str] = None
    process: Optional[subprocess.Popen] = None
    current_track: Optional[str] = None
    current_track_id: Optional[int] = None
    is_playing: bool = False
    current_position: float = 0.0
    duration: float = 0.0
    playback_source: Optional[str] = None
    current_session_id: Optional[int] = None
    playback_started_at: Optional[float] = None  # NEW: Unix timestamp
```

### Step 2: Add validation constants
**Location:** After imports (~line 19)

```python
# Minimum valid duration (seconds) - durations below this indicate metadata errors
MIN_VALID_DURATION = 10.0

# Minimum playback time before allowing "track finished" (seconds)
MIN_PLAYBACK_TIME = 3.0
```

### Step 3: Enhanced duration loading with stability checks
**Location:** Lines 243-253 (replace entire polling block in play_file)

```python
# Wait for file metadata with stability checks
max_wait = 2.0  # Increased from 0.5s for network streams
poll_interval = 0.05
elapsed = 0.0
duration_loaded = False
last_duration = None
stable_reads = 0
required_stable_reads = 2

logger.debug(f"Loading file metadata for: {local_path}")

while elapsed < max_wait:
    duration = get_mpv_property(state.socket_path, "duration")

    if duration and duration > 0:
        if last_duration is not None and abs(duration - last_duration) < 0.1:
            stable_reads += 1
            if stable_reads >= required_stable_reads:
                logger.info(
                    f"Metadata loaded: duration={duration:.2f}s, elapsed={elapsed:.3f}s"
                )
                duration_loaded = True
                break
        else:
            stable_reads = 0

        last_duration = duration

    time.sleep(poll_interval)
    elapsed += poll_interval

if not duration_loaded:
    logger.warning(
        f"Metadata load incomplete after {max_wait}s: duration={last_duration}"
    )
```

**Rationale:**
- 2-second timeout accommodates slow filesystems/network streams
- Stability check (2 consecutive stable reads) prevents accepting transitional values
- Enhanced logging for diagnostics

### Step 4: Set playback_started_at timestamp
**Location:** Lines 271-279 (in state._replace call within play_file)

```python
import time as time_module

updated_state = update_player_status(
    state._replace(
        current_track=local_path,
        current_track_id=track_id,
        is_playing=True,
        playback_source="mpv",
        current_session_id=session_id,
        playback_started_at=time_module.time(),  # NEW
    )
)
```

### Step 5: Enhanced is_track_finished with multiple safeguards
**Location:** Lines 543-577 (replace entire function)

```python
def is_track_finished(state: PlayerState) -> bool:
    """Check if track finished with multiple validation layers.

    Safeguards:
    1. Minimum playback time (prevents incomplete metadata issues)
    2. Duration sanity check (detects corrupted/incomplete metadata)
    3. Position-based completion check
    4. EOF flag validation (with position confirmation)
    """
    if not is_mpv_running(state):
        return False

    position = get_mpv_property(state.socket_path, "time-pos") or 0.0
    duration = get_mpv_property(state.socket_path, "duration") or 0.0
    eof = get_mpv_property(state.socket_path, "eof-reached")

    # SAFEGUARD 1: Minimum playback time
    import time
    playback_elapsed = 0.0
    if state.playback_started_at is not None:
        playback_elapsed = time.time() - state.playback_started_at
        if playback_elapsed < MIN_PLAYBACK_TIME:
            logger.debug(
                f"is_track_finished: Too early (elapsed={playback_elapsed:.2f}s)"
            )
            return False

    # SAFEGUARD 2: Duration sanity check
    duration_is_suspicious = 0 < duration < MIN_VALID_DURATION
    if duration_is_suspicious:
        logger.warning(
            f"is_track_finished: Suspicious duration={duration:.2f}s, "
            f"ignoring position-based checks"
        )
        # Only trust eof when position is very close
        if eof is True and position >= duration - 0.1:
            return True
        return False

    # SAFEGUARD 3: Position-based check (primary)
    finished_by_position = duration > 0 and position >= duration - 0.5

    # SAFEGUARD 4: EOF flag check (secondary)
    finished_by_eof = eof is True and duration > 0 and position >= duration - 1.0

    result = finished_by_position or finished_by_eof

    logger.debug(
        "is_track_finished: pos={:.2f}, dur={:.2f}, elapsed={:.2f}s, "
        "suspicious={}, by_pos={}, by_eof={}, result={}",
        position, duration, playback_elapsed, duration_is_suspicious,
        finished_by_position, finished_by_eof, result,
    )

    return result
```

**Rationale:**
- Multi-layered defense prevents false positives from multiple failure modes
- Minimum playback time (3s) prevents early triggers during metadata loading
- Duration sanity check (10s minimum) catches incomplete metadata
- Enhanced logging aids diagnosis

### Step 6: Clear playback_started_at on stop
**Location:** Lines 330-348 (stop_playback function, in state._replace)

```python
return state._replace(
    current_track=None,
    current_track_id=None,
    is_playing=False,
    current_position=0.0,
    duration=0.0,
    current_session_id=None,
    playback_started_at=None,  # NEW
), True
```

## Acceptance Criteria

### Functional Tests
1. ✓ Network streams (SoundCloud/Spotify) play fully without restart
2. ✓ High-bitrate local files (FLAC/Opus) load metadata correctly
3. ✓ Fast local files (MP3) show no regression
4. ✓ Comparison mode autoplay still works
5. ✓ Songs don't restart after 1-2 seconds

### Logging Verification
Monitor logs to verify:
```bash
tail -f ~/.local/state/music-minion/logs/music-minion.log | grep "is_track_finished\|Metadata loaded"
```

Expected log output:
- "Metadata loaded: duration=XXX.XXs, elapsed=X.XXXs" on successful load
- "is_track_finished: pos=X.XX, dur=X.XX, elapsed=X.XXs..." debug logs
- "Suspicious duration=X.XXs" warnings for incomplete metadata

### Edge Cases
- Very short files (<10 seconds) should still play correctly
- Corrupted files should fail gracefully with warning logs
- Rapid skip commands shouldn't trigger false autoplay

## Dependencies
None - This is an independent fix for the playback system.

## Related Files (No Changes)
- `src/music_minion/ui/blessed/app.py` - Calls is_track_finished in main loop (lines 519-538)
