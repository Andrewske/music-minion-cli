# Step 3: Testing Comparison Autoplay

## Objective
Verify the comparison autoplay implementation works correctly across all scenarios and edge cases.

## Prerequisites
- Step 1: Helper function added ✓
- Step 2: Integration into poll_player_state() ✓
- Application runs without syntax errors ✓

## Test Environment Setup

1. **Start the application**:
   ```bash
   music-minion
   ```

2. **Enter comparison mode**:
   - Press `C` to start a comparison session
   - Wait for tracks A and B to load

## Test Scenarios

### Test 1: Basic A↔B Loop ✓
**Purpose**: Verify continuous autoplay between comparison tracks.

**Steps**:
1. Start comparison session (Press `C`)
2. Play track A (highlight A, press Space)
3. Let track A play to completion (~30 seconds or seek to end)
4. Observe track B starts automatically
5. Let track B play to completion
6. Observe track A starts automatically again

**Expected Results**:
- ✅ Track B starts automatically when A finishes
- ✅ Track A starts automatically when B finishes
- ✅ Command history shows: `♪ Comparison autoplay: [Track Name]`
- ✅ "▶ Playing..." indicator switches to correct track
- ✅ No "Now playing" message duplication

**Verification**:
```
Command History:
♪ Now playing: Track A Title
   Duration: 3:45
♪ Comparison autoplay: Track B Title
   Duration: 4:12
♪ Comparison autoplay: Track A Title
   Duration: 3:45
```

---

### Test 2: Pause Interrupt ✓
**Purpose**: Verify loop stops when user pauses.

**Steps**:
1. Start A↔B autoplay loop (from Test 1)
2. When track switches automatically, immediately press Space to pause
3. Wait 10 seconds
4. Verify no autoplay occurs while paused

**Expected Results**:
- ✅ Autoplay stops when track is paused
- ✅ No automatic track switch while paused
- ✅ Resume (Space) continues playing current track, not switching

**Verification**: Track stays paused, no history messages added.

---

### Test 3: Manual Track Override ✓
**Purpose**: Verify loop stops when user manually plays different track.

**Steps**:
1. Start A↔B autoplay loop
2. Press `Esc` to exit comparison (or press `L` to view library)
3. Manually play a different track from library
4. Let that track finish

**Expected Results**:
- ✅ Comparison autoplay stops when non-comparison track plays
- ✅ Global autoplay resumes for library tracks
- ✅ No comparison autoplay messages in history

**Verification**: Check command history for normal autoplay messages, not comparison messages.

---

### Test 4: Exit Comparison Mode ✓
**Purpose**: Verify loop stops when comparison exits.

**Steps**:
1. Start A↔B autoplay loop
2. Press `Esc` or `Q` to exit comparison mode
3. Observe what happens when current track finishes

**Expected Results**:
- ✅ Comparison mode exits
- ✅ Global autoplay resumes (plays next library/playlist track)
- ✅ No comparison autoplay after exit

**Verification**: `comparison.active = False`, global autoplay kicks in.

---

### Test 5: Complete Comparison Session ✓
**Purpose**: Verify loop stops when target comparisons reached.

**Steps**:
1. Start comparison session with low target (e.g., 5 comparisons)
2. Start A↔B autoplay loop
3. Make ratings to reach target
4. Session auto-exits
5. Let current track finish

**Expected Results**:
- ✅ Session exits after target reached
- ✅ Global autoplay resumes
- ✅ No comparison autoplay after session complete

**Verification**: Comparison mode closes automatically, global autoplay works.

---

### Test 6: Non-Comparison Track During Comparison ✓
**Purpose**: Verify bypass when non-comparison track plays during comparison mode.

**Steps**:
1. Enter comparison mode (tracks A and B loaded)
2. **Don't play A or B** - instead:
   - Press `L` to view library
   - Play a different track (not A or B)
3. Let that track finish
4. Observe autoplay behavior

**Expected Results**:
- ✅ Comparison autoplay does NOT trigger (track is not A or B)
- ✅ Global autoplay triggers instead
- ✅ Early return logic: `if current_track_id not in (a_id, b_id): return ctx, ui_state, False`

**Verification**:
- Command history shows normal autoplay message (not comparison message)
- Global autoplay logic runs (plays next library track)

---

### Test 7: History Message Draining ✓
**Purpose**: Verify no message loss or duplication.

**Steps**:
1. Start A↔B autoplay loop
2. Let track A finish → B autoplays
3. Examine command history carefully

**Expected Results**:
- ✅ See standard "Now playing" messages from `play_track()`
- ✅ See "Comparison autoplay" message
- ✅ No duplicate messages
- ✅ No missing duration/DJ info messages

**Verification**: Command history should look like:
```
♪ Now playing: Track B Title
   Duration: 4:12
   DJ: Mixed in A♯ Minor
♪ Comparison autoplay: Track B Title
```

---

### Test 8: Highlight Independence ✓
**Purpose**: Verify highlight doesn't auto-switch during autoplay.

**Steps**:
1. Start comparison mode
2. Highlight track A (should be highlighted by default)
3. Play track B (Down arrow, then Space)
4. Let track B finish → A autoplays
5. Check which track is highlighted

**Expected Results**:
- ✅ Highlight stays on B even though A is now playing
- ✅ "▶ Playing..." indicator shows on A
- ✅ User can still navigate with Up/Down arrows
- ✅ Highlight represents selection, not playback state

**Verification**: Visual inspection of UI - highlighted track ≠ playing track.

---

### Test 9: Database Lookup Failure ✓
**Purpose**: Verify graceful fallback when opposite track not found.

**Steps**:
1. This is harder to test without mocking, but check error handling:
2. Look for `if not db_track:` in helper function
3. Verify it returns `(ctx, ui_state, False)` to fall through

**Expected Results**:
- ✅ If DB lookup fails, global autoplay runs instead
- ✅ No crashes or exceptions
- ✅ User sees normal autoplay behavior

**Verification**: Code review of helper function error handling.

---

## Performance Testing

### Test 10: No Extra Polling ✓
**Purpose**: Verify no performance impact.

**Steps**:
1. Start A↔B autoplay loop
2. Monitor CPU usage
3. Verify polling happens at existing 10Hz rate

**Expected Results**:
- ✅ No additional polling overhead
- ✅ Piggybacks on existing `poll_player_state()` calls
- ✅ No noticeable lag or CPU spike

---

## Regression Testing

### Test 11: Global Autoplay Still Works ✓
**Purpose**: Ensure global autoplay unaffected.

**Steps**:
1. **Don't** enter comparison mode
2. Play a track from library
3. Let it finish
4. Verify next track autoplays normally

**Expected Results**:
- ✅ Global autoplay works as before
- ✅ No comparison autoplay interference
- ✅ Playlist/shuffle logic unchanged

---

### Test 12: Comparison Play/Pause Still Works ✓
**Purpose**: Ensure manual comparison controls unaffected.

**Steps**:
1. Enter comparison mode
2. Manually play track A (Space)
3. Pause track A (Space)
4. Switch to track B (Down, Space)
5. Verify all manual controls work

**Expected Results**:
- ✅ Manual play/pause works as before
- ✅ Highlight switching works
- ✅ No interference from autoplay logic

---

## Test Summary Checklist

After running all tests, verify:

- [ ] Basic A↔B loop works continuously
- [ ] Pause stops autoplay
- [ ] Manual override stops comparison autoplay
- [ ] Exit comparison stops autoplay
- [ ] Session complete stops autoplay
- [ ] Non-comparison track bypasses comparison autoplay
- [ ] History messages drain correctly (no loss/duplication)
- [ ] Highlight stays independent of playback
- [ ] Error handling works (DB lookup failure)
- [ ] No performance impact
- [ ] Global autoplay still works
- [ ] Manual comparison controls still work

## Known Issues / Edge Cases

If you encounter issues, check:

1. **Messages Missing**: Ensure `drain_pending_history_messages()` is called
2. **Wrong Track Plays**: Check track ID extraction uses fallback pattern
3. **Duplicate Autoplay**: Verify `if not track_changed:` wraps global autoplay
4. **Crashes**: Check null safety for `comparison.track_a`, `comparison.track_b`, `current_id`

## Completion Criteria

All tests pass ✅ → Implementation complete!

If any test fails → Review corresponding step in Step 1 or Step 2 for issues.
