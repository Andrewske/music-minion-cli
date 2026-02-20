---
task: 03-player-integration
status: done
depends: [01-domain-history-functions]
files:
  - path: web/backend/routers/player.py
    action: modify
---

# Integrate History Recording with Player

## Context
Hook history recording into the player's play/skip/pause actions. Every play() call creates a history entry; every stop action closes it with duration.

## Files to Modify/Create
- web/backend/routers/player.py (modify)

## Implementation Details

### Add to `_playback_state` dict:
```python
"current_history_id": None,  # Track active history entry
"duration_ms": 0,            # Accumulated listening time (reset each track)
```

**Important distinction:**
- `position_ms`: Current playback position (for resume/scrubber UI)
- `duration_ms`: Actual time spent listening (for history/stats)

### Modify `POST /player/play` endpoint:

After initializing the queue but before broadcasting state:

```python
# End previous history entry if exists
if _playback_state.get("current_history_id"):
    from music_minion.domain.radio.history import end_play
    current_position = int(_playback_state.get("position_ms", 0))
    end_play(_playback_state["current_history_id"], final_duration)

# Start new history entry
from music_minion.domain.radio.history import start_play
history_id = start_play(
    track_id=_playback_state["current_track"]["id"],
    source_type="local"  # or derive from track source
)
_playback_state["current_history_id"] = history_id
```

### Modify `POST /player/next` endpoint:

Add optional query param `reason`: `skip` (default) or `completed`.

```python
@router.post("/next")
async def next_track(reason: str = "skip", db=Depends(get_db)):
```

Before switching to next track, close current history entry:
```python
if _playback_state.get("current_history_id"):
    from music_minion.domain.radio.history import end_play
    final_duration = _calculate_final_duration()
    end_play(_playback_state["current_history_id"], final_duration, reason=reason)
    _playback_state["current_history_id"] = None
```

Then after setting the new track, start a new entry (similar to play endpoint).

**Frontend change**: Call `/player/next?reason=completed` when audio `ended` event fires.
Call `/player/next` (or `/player/next?reason=skip`) on manual skip.

### Modify `POST /player/seek` endpoint:

Snapshot elapsed time into duration_ms BEFORE seeking:
```python
# Accumulate listening time before seek
if _playback_state.track_started_at:
    elapsed = time.time() - _playback_state.track_started_at
    _playback_state.duration_ms += int(elapsed * 1000)

# Then do normal seek (position_ms = seek target, restart timer)
_playback_state.position_ms = request.position_ms
_playback_state.track_started_at = time.time() if _playback_state.is_playing else None
```

### Modify `POST /player/pause` endpoint:

Add duration accumulation (similar to seek):
```python
if _playback_state.track_started_at:
    elapsed = time.time() - _playback_state.track_started_at
    _playback_state.duration_ms += int(elapsed * 1000)
    _playback_state.position_ms += int(elapsed * 1000)  # Keep for resume position
_playback_state.track_started_at = None
```

**Do NOT call end_play() on pause** - this would corrupt duration if user resumes later.

### Helper function:
```python
def _calculate_final_duration() -> int:
    """Calculate total listening duration in ms (accumulated + current segment)."""
    duration = int(_playback_state.get("duration_ms", 0))

    if _playback_state.get("track_started_at"):
        elapsed = int((time.time() - _playback_state["track_started_at"]) * 1000)
        duration += elapsed

    return duration
```

### Reset duration on new track:

In `POST /player/play`, after setting current_track:
```python
_playback_state.duration_ms = 0  # Reset for new track
```

In `POST /player/next`, after advancing to next track:
```python
_playback_state.duration_ms = 0  # Reset for new track
```

## Verification
1. Start web mode: `music-minion --web`
2. Open browser, play a track
3. Check database: `sqlite3 music_minion.db "SELECT * FROM radio_history ORDER BY id DESC LIMIT 5"`
4. Verify entry has started_at set
5. Skip track, verify ended_at and position_ms are populated
6. Play another track, verify new entry created
