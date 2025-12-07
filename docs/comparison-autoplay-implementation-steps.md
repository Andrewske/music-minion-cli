# Comparison Autoplay Implementation Steps

## Overview

This directory contains step-by-step instructions for implementing comparison track autoplay. Each step is self-contained with code, rationale, and verification steps.

## Implementation Order

Follow these steps in sequence:

### 📋 Step 1: Add Helper Function
**File**: `comparison-autoplay-step-1-helper-function.md`

**What**: Add `_handle_comparison_autoplay()` helper function to `src/music_minion/ui/blessed/app.py`

**Key Features**:
- Robust track ID extraction (handles "id" or "track_id" keys)
- History message draining (prevents message loss)
- Force playlist ID to prevent playlist association
- Early returns for graceful fallback

**Estimated Time**: 10 minutes

---

### 🔗 Step 2: Integrate into poll_player_state()
**File**: `comparison-autoplay-step-2-integrate-poll-player-state.md`

**What**: Modify `poll_player_state()` to call the helper before global autoplay

**Key Changes**:
- Extract `comparison` and `current_id` variables
- Add conditional check for comparison mode
- Wrap global autoplay in `if not track_changed:`

**Estimated Time**: 5 minutes

---

### ✅ Step 3: Testing
**File**: `comparison-autoplay-step-3-testing.md`

**What**: Comprehensive testing across 12 scenarios

**Test Coverage**:
- Basic A↔B loop
- Pause interrupt
- Manual override
- Exit comparison
- Session completion
- Non-comparison track bypass
- History message draining
- Highlight independence
- Error handling
- Performance
- Regression tests

**Estimated Time**: 30-45 minutes

---

## Quick Start

```bash
# 1. Read Step 1
cat docs/comparison-autoplay-step-1-helper-function.md

# 2. Add helper function to app.py
# (See Step 1 for exact code and location)

# 3. Verify syntax
uv run python -m py_compile src/music_minion/ui/blessed/app.py

# 4. Read Step 2
cat docs/comparison-autoplay-step-2-integrate-poll-player-state.md

# 5. Modify poll_player_state()
# (See Step 2 for exact changes)

# 6. Verify syntax again
uv run python -m py_compile src/music_minion/ui/blessed/app.py

# 7. Run application and test
music-minion

# 8. Follow Step 3 testing scenarios
cat docs/comparison-autoplay-step-3-testing.md
```

## Files Modified

- **`src/music_minion/ui/blessed/app.py`**: Only file requiring changes
  - Add `_handle_comparison_autoplay()` helper function (~50 lines)
  - Modify `poll_player_state()` autoplay section (~10 lines changed)

## Total Changes

- **Lines Added**: ~60
- **Lines Modified**: ~10
- **Files Changed**: 1
- **Breaking Changes**: None
- **Backwards Compatibility**: Full

## Critical Implementation Details

### 1. History Message Draining
```python
# CRITICAL: Must drain messages after play_track()
for msg, color in drain_pending_history_messages():
    ui_state = add_history_line(ui_state, msg, color)
```

### 2. Robust Track ID Extraction
```python
# Handles both "id" and "track_id" keys
a_id = comparison.track_a.get("track_id") or comparison.track_a.get("id")
```

### 3. Force Playlist ID
```python
# Prevents playlist association for comparison tracks
ctx, _ = play_track(ctx, track_obj, None, force_playlist_id=None)
```

### 4. Fall-Through Logic
```python
# Early returns allow global autoplay to run
if current_track_id not in (a_id, b_id):
    return ctx, ui_state, False  # track_changed=False
```

## Design Decisions Reference

See `comparison-autoplay-implementation-plan.md` section "Key Design Decisions" for detailed rationale on:
1. History message handling
2. Robust track ID extraction
3. Independent highlight state
4. Force playlist ID usage
5. Helper function extraction

## Success Criteria

Implementation is complete when:
- ✅ All 12 test scenarios pass (Step 3)
- ✅ No syntax errors
- ✅ No message loss or duplication
- ✅ Global autoplay still works
- ✅ No performance impact

## Rollback Plan

If issues arise:
```bash
# Revert changes
git checkout src/music_minion/ui/blessed/app.py

# Or manually remove:
# 1. _handle_comparison_autoplay() function
# 2. Comparison autoplay block in poll_player_state()
# 3. Restore original "if player.is_track_finished():" section
```

## Additional Resources

- **Full Plan**: `comparison-autoplay-implementation-plan.md`
- **Project Style Guide**: `../CLAUDE.md`
- **Codebase Patterns**: `../ai-learnings.md`

## Questions?

If unclear about any step:
1. Check the detailed plan: `comparison-autoplay-implementation-plan.md`
2. Review existing code patterns in `src/music_minion/ui/blessed/events/commands/executor.py` (see `_handle_comparison_play_track_cmd`)
3. Check output system: `src/music_minion/core/output.py`
