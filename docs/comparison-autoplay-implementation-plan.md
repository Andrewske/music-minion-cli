# Comparison Track Autoplay Implementation Plan

## Overview

Implement autoplay functionality for track comparison mode where finishing one comparison track automatically plays the other track, creating a continuous A↔B loop until the user pauses or exits comparison mode.

### Key Improvements (Post-Analysis)

This plan was refined through multi-agent analysis (Architect, Research, Coder perspectives) to ensure production quality:

✅ **History Message Race Condition Fix** - Added `drain_pending_history_messages()` to prevent message loss
✅ **Robust Track ID Extraction** - Fallback pattern handles inconsistent dict keys (`"id"` vs `"track_id"`)
✅ **Helper Function Extraction** - Follows project style guide (≤20 lines, ≤3 nesting)
✅ **Independent Highlight State** - Documented UX decision to keep highlight user-controlled
✅ **Force Playlist ID** - Prevents playlist association for comparison tracks (analytics accuracy)
✅ **Expanded Testing** - Added edge case for non-comparison track finishing during comparison mode

## Current Behavior

- **Comparison Mode**: Users can manually play tracks A or B using Space bar when highlighted
- **Track End Detection**: Global autoplay logic in `poll_player_state` detects when any track finishes
- **Global Autoplay**: When a track ends, the system automatically plays the next track based on shuffle mode and active playlist
- **Comparison Context Loss**: When a comparison track ends, the global autoplay kicks in and plays a regular library/playlist track, breaking the comparison session

## Desired Behavior

When in comparison mode and playing one of the comparison tracks:

- **Track A ends** → Automatically play Track B
- **Track B ends** → Automatically play Track A  
- **Continuous Loop**: A ↔ B autoplay continues indefinitely
- **Exit Conditions**: Loop stops when user:
  - Pauses playback (Space bar)
  - Exits comparison mode (Esc/Q)
  - Manually starts a different track
  - Completes the comparison session

## Implementation Approach

### Hook Location
Add comparison-specific autoplay logic in `poll_player_state()` in `src/music_minion/ui/blessed/app.py`, **before** the existing global autoplay logic.

### Key Components

1. **Track End Detection**: Reuse existing `player.is_track_finished()` check
2. **Comparison Mode Check**: Verify `ui_state.comparison.active` is True
3. **Current Track Identification**: Check if `ctx.player_state.current_track_id` matches either comparison track
4. **Opposite Track Selection**: Play the other comparison track (A→B or B→A)
5. **Playback Path**: Reuse existing comparison play command path for consistency
6. **History Message Handling**: Drain queued messages from `play_track()` to prevent message loss

### Code Structure

**Helper Function** (add before `poll_player_state()` around line 350):

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

**Usage in `poll_player_state()`** (around line 421):

```python
# Check if track has finished and auto-advance
track_changed = False
if player.is_track_finished(ctx.player_state) and ctx.music_tracks:
    comparison = ui_state.comparison
    current_id = ctx.player_state.current_track_id

    # NEW: Comparison autoplay (before global autoplay)
    if comparison.active and comparison.track_a and comparison.track_b and current_id:
        ctx, ui_state, track_changed = _handle_comparison_autoplay(
            ctx, ui_state, comparison, current_id
        )

    # EXISTING: Global autoplay (only if comparison didn't handle it)
    if not track_changed:
        # Get available tracks (excluding archived ones)
        available_tracks = get_available_tracks(ctx)
        # ... rest of existing global autoplay logic
```

## Files to Modify

### Primary Changes
- **`src/music_minion/ui/blessed/app.py`**: Add comparison autoplay logic in `poll_player_state()`

### Supporting Files (No Changes Needed)
- **`src/music_minion/ui/blessed/events/commands/executor.py`**: `_handle_comparison_play_track_cmd()` - reuse existing path
- **`src/music_minion/core/database.py`**: `db_track_to_library_track()` - reuse existing conversion
- **`src/music_minion/domain/playback/player.py`**: `is_track_finished()` - reuse existing detection

## Edge Cases & Considerations

### Playback State Management
- **Pausing**: `is_track_finished()` only triggers on actual track end, not pause - loop stops when user pauses
- **Manual Track Changes**: If user manually plays a non-comparison track, comparison autoplay is bypassed
- **Comparison Exit**: When `comparison.active` becomes False, autoplay falls back to global behavior

### UI State Consistency
- **Playing Indicators**: Existing status re-query after `track_changed` ensures UI shows correct "▶ Playing..." on A/B
- **Highlight Preservation**: Autoplay doesn't change `comparison.highlighted` - rating selection remains user-controlled
  - **Rationale**: Highlight represents rating selection focus, not playback state
  - Visual "▶ Playing..." indicator already shows which track is active
  - User can read track A metadata while track B plays
  - Preserves existing mental model (highlight = selection, not playback)
- **History Messages**: Drains queued messages from `play_track()` first, then adds comparison-specific notification
  - **Critical**: Must call `drain_pending_history_messages()` after `play_track()` to prevent message loss
  - Matches pattern in `_handle_comparison_play_track_cmd` (executor.py:334-335)

### Error Handling
- **Track Not Found**: If opposite track DB lookup fails, fall through to global autoplay
- **Playback Failure**: If `play_track()` fails, fall through to global autoplay  
- **Invalid State**: Robust null checks prevent crashes if comparison state is malformed

## Testing Scenarios

1. **Basic Loop**: Play A → A ends → B plays automatically → B ends → A plays automatically
2. **Pause Interrupt**: Play A → A ends → B starts → User presses Space → B pauses → No further autoplay
3. **Manual Override**: During A↔B loop, user manually plays different track → Loop stops
4. **Exit Comparison**: During loop, user presses Esc → Comparison exits → Global autoplay resumes
5. **Session Complete**: During loop, user makes enough ratings to complete session → Comparison exits
6. **Non-Comparison Track**: User in comparison mode → Manually plays library track (not A or B) → Track finishes → Global autoplay triggers (comparison autoplay bypassed)
   - Validates: `if current_track_id not in (a_id, b_id)` early return logic

## Benefits

- **Seamless Comparison**: Eliminates manual Space bar presses between tracks
- **Efficient Rating**: Faster comparison workflow for large rating sessions  
- **User Control**: Loop respects pause/exit actions, doesn't interfere with manual control
- **Consistent UX**: Reuses existing playback and UI update paths
- **Backward Compatible**: No changes to existing comparison or global autoplay behavior

## Implementation Notes

- **Helper Function Extraction**: Logic extracted to `_handle_comparison_autoplay()` helper (≤20 lines, ≤3 nesting - follows project style guide)
- **Reuse Existing Code**: Leverages comparison play command, track conversion, and autoplay infrastructure
- **Performance**: No additional polling - piggybacks on existing 10Hz player status checks
- **Maintainability**: Logic is self-contained and clearly separated from global autoplay

## Key Design Decisions

### 1. History Message Handling
**Decision**: Drain `_pending_history_messages` after `play_track()` before adding custom message

**Rationale**:
- `play_track()` calls `log()` which queues messages in `_pending_history_messages`
- Without draining, standard "Now playing" messages are lost
- Matches existing pattern in `_handle_comparison_play_track_cmd` (executor.py:334-335)
- Prevents message duplication/loss race conditions

### 2. Robust Track ID Extraction
**Decision**: Use fallback pattern `get("track_id") or get("id")`

**Rationale**:
- Comparison track dicts use inconsistent keys (`"id"` vs `"track_id"`)
- Existing code in executor.py:312 already uses this pattern
- Prevents silent failures when tracks use different key formats

### 3. Independent Highlight State
**Decision**: Don't auto-update `comparison.highlighted` during autoplay

**Rationale**:
- Highlight represents **rating selection focus**, not playback state
- Visual "▶ Playing..." indicator already shows which track is active
- User may want to read track A metadata while track B plays
- Preserves existing mental model (highlight = user selection, not system state)

### 4. Force Playlist ID
**Decision**: Use `force_playlist_id=None` for comparison track playback

**Rationale**:
- Prevents comparison tracks from being associated with playlists
- Ensures listening analytics accuracy (comparison ≠ playlist listening)
- Matches pattern in `_handle_comparison_play_track_cmd` (executor.py:331)

### 5. Helper Function Extraction
**Decision**: Extract logic to `_handle_comparison_autoplay()` helper function

**Rationale**:
- Inline code would be 20+ lines with 4-5 nesting levels
- Project style guide: ≤20 lines, ≤3 nesting per function (CLAUDE.md)
- Improves testability and maintainability
- Follows functional programming pattern with explicit state passing</content>
<parameter name="filePath">/home/kevin/coding/music-minion-cli/docs/comparison-autoplay-implementation-plan.md