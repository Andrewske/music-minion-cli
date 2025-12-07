# Step 2: Integrate Helper into poll_player_state()

## Objective
Modify the `poll_player_state()` function to call `_handle_comparison_autoplay()` **before** global autoplay logic.

## File Location
`src/music_minion/ui/blessed/app.py`

## Target Function
`poll_player_state()` (starts around line 357)

## Modification Location
Find the section that handles track finishing and autoplay (around line 421). This should look like:

```python
# Check if track has finished and auto-advance
track_changed = False
if player.is_track_finished(ctx.player_state) and ctx.music_tracks:
    # Get available tracks (excluding archived ones)
    available_tracks = get_available_tracks(ctx)

    if available_tracks:
        # Get next track based on shuffle mode and active playlist
        result = get_next_track(ctx, available_tracks)
        # ... rest of global autoplay logic
```

## Code Changes

### BEFORE (Current Code)
```python
# Check if track has finished and auto-advance
track_changed = False
if player.is_track_finished(ctx.player_state) and ctx.music_tracks:
    # Get available tracks (excluding archived ones)
    available_tracks = get_available_tracks(ctx)
```

### AFTER (Modified Code)
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
```

## Key Implementation Details

### 1. Variable Extraction
```python
comparison = ui_state.comparison
current_id = ctx.player_state.current_track_id
```
**Why**: Extract these once for clarity and to avoid repeated attribute access.

### 2. Condition Check
```python
if comparison.active and comparison.track_a and comparison.track_b and current_id:
```
**Why**: Only attempt comparison autoplay if:
- Comparison mode is active
- Both tracks A and B are loaded
- Current track ID is available

### 3. Track Changed Flag
```python
ctx, ui_state, track_changed = _handle_comparison_autoplay(...)
```
**Why**: The helper returns whether it handled the autoplay. If `track_changed=True`, skip global autoplay.

### 4. Conditional Global Autoplay
```python
if not track_changed:
    # Get available tracks (excluding archived ones)
    available_tracks = get_available_tracks(ctx)
```
**Why**: Only run global autoplay if comparison autoplay didn't trigger. This prevents double-autoplay.

## Complete Modified Section

Here's the full section with context:

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

        if available_tracks:
            # Get next track based on shuffle mode and active playlist
            result = get_next_track(ctx, available_tracks)

            if result:
                track, position = result
                # Play next track silently (no print in UI mode)
                ctx, _ = play_track(ctx, track, position)
                track_changed = True

                # Add autoplay notification to command history
                from ...domain import library

                ui_state = add_history_line(
                    ui_state,
                    f"♪ Now playing: {library.get_display_name(track)}",
                    "cyan",
                )
                if track.duration:
                    ui_state = add_history_line(
                        ui_state,
                        f"   Duration: {library.get_duration_str(track)}",
                        "blue",
                    )

                dj_info = library.get_dj_info(track)
                if dj_info != "No DJ metadata":
                    ui_state = add_history_line(
                        ui_state, f"   {dj_info}", "magenta"
                    )

# If track changed, re-query player status to get new track info
if track_changed:
    # ... existing re-query logic
```

## Verification Steps

After making the changes:

1. **Syntax Check**:
   ```bash
   uv run python -m py_compile src/music_minion/ui/blessed/app.py
   ```

2. **Visual Inspection**:
   - Verify the comparison autoplay block is **before** `if not track_changed:`
   - Confirm the global autoplay logic is wrapped in `if not track_changed:`
   - Check that `track_changed` is initialized to `False` at the start

3. **Indentation**: Ensure proper indentation (4 spaces per level)

4. **No Syntax Errors**: Look for:
   - Matching parentheses
   - Correct variable names (`comparison`, `current_id`, `track_changed`)
   - Proper function call syntax

## Expected Behavior

After this change:
- When a comparison track finishes → `_handle_comparison_autoplay()` runs first
- If it returns `track_changed=True` → Global autoplay is skipped
- If it returns `track_changed=False` → Global autoplay runs as usual
- Non-comparison tracks → Bypass comparison logic, global autoplay runs normally

## Next Step

Proceed to `comparison-autoplay-step-3-testing.md` for comprehensive testing scenarios.
