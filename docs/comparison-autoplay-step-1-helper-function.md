# Step 1: Add Comparison Autoplay Helper Function

## Objective
Add the `_handle_comparison_autoplay()` helper function to `src/music_minion/ui/blessed/app.py` that handles the A↔B autoplay loop logic.

## File Location
`src/music_minion/ui/blessed/app.py`

## Insert Location
Add this function **before** the `poll_player_state()` function (around line 350).

## Code to Add

```python
def _handle_comparison_autoplay(
    ctx: AppContext,
    ui_state: UIState,
    comparison: ComparisonState,
    current_track_id: int,
) -> tuple[AppContext, UIState, bool]:
    """
    Handle autoplay for comparison mode (A ↔ B loop).

    Returns:
        (ctx, ui_state, track_changed) - track_changed=True if autoplay triggered
    """
    from music_minion.core import database
    from music_minion.domain import library
    from music_minion.commands.playback import play_track
    from music_minion.core.output import drain_pending_history_messages

    # Robust track ID extraction (handles "id" or "track_id" keys)
    a_id = comparison.track_a.get("track_id") or comparison.track_a.get("id")
    b_id = comparison.track_b.get("track_id") or comparison.track_b.get("id")

    # Only trigger if current track is one of the comparison tracks
    if current_track_id not in (a_id, b_id):
        return ctx, ui_state, False

    # Determine opposite track
    other_id = b_id if current_track_id == a_id else a_id

    # Get track from database
    db_track = database.get_track_by_id(other_id)
    if not db_track:
        return ctx, ui_state, False  # Fall through to global autoplay

    # Play opposite track (force_playlist_id=None prevents playlist association)
    track_obj = database.db_track_to_library_track(db_track)
    ctx, _ = play_track(ctx, track_obj, None, force_playlist_id=None)

    # CRITICAL: Drain messages queued by play_track() (prevents message loss)
    for msg, color in drain_pending_history_messages():
        ui_state = add_history_line(ui_state, msg, color)

    # Add comparison-specific notification
    ui_state = add_history_line(
        ui_state,
        f"♪ Comparison autoplay: {library.get_display_name(track_obj)}",
        "cyan",
    )

    return ctx, ui_state, True
```

## Critical Implementation Details

### 1. Robust Track ID Extraction
```python
a_id = comparison.track_a.get("track_id") or comparison.track_a.get("id")
b_id = comparison.track_b.get("track_id") or comparison.track_b.get("id")
```
**Why**: Comparison track dicts use inconsistent keys. This fallback pattern ensures compatibility.

### 2. History Message Draining
```python
for msg, color in drain_pending_history_messages():
    ui_state = add_history_line(ui_state, msg, color)
```
**Why**: `play_track()` queues messages via `log()`. Without draining, these messages are lost, causing a race condition.

### 3. Force Playlist ID
```python
ctx, _ = play_track(ctx, track_obj, None, force_playlist_id=None)
```
**Why**: Prevents comparison tracks from being associated with playlists. Ensures listening analytics accuracy.

### 4. Early Returns
```python
if current_track_id not in (a_id, b_id):
    return ctx, ui_state, False

if not db_track:
    return ctx, ui_state, False
```
**Why**: Explicit fall-through to global autoplay when conditions aren't met. Returning `track_changed=False` allows the existing autoplay logic to run.

## Function Signature

**Parameters**:
- `ctx: AppContext` - Current application context
- `ui_state: UIState` - Current UI state
- `comparison: ComparisonState` - Comparison session state
- `current_track_id: int` - ID of the track that just finished

**Returns**:
- `tuple[AppContext, UIState, bool]` - Updated context, updated UI state, and whether track changed

## Verification Steps

After adding the function:

1. **Syntax Check**: Run `uv run python -m py_compile src/music_minion/ui/blessed/app.py`
2. **Import Check**: Verify all imports are available:
   - `from music_minion.core import database`
   - `from music_minion.domain import library`
   - `from music_minion.commands.playback import play_track`
   - `from music_minion.core.output import drain_pending_history_messages`

3. **Type Hints**: Ensure type hints are correct (no `Any` types)

## Next Step

Proceed to `comparison-autoplay-step-2-integrate-poll-player-state.md` to integrate this helper into the main polling loop.
