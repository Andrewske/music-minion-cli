# Autoplay Testing Guide

## Automated Tests (Completed ✅)
```bash
uv run python test_autoplay.py
```

All core functionality tests passed:
1. ✅ Track completion detection
2. ✅ EOF property querying
3. ✅ Duration fallback logic

## Manual Testing Scenarios

### Test 1: Basic Autoplay (Shuffle Mode)

**Setup:**
1. Start music-minion: `uv run music-minion`
2. Verify shuffle is ON: `shuffle` (should show "ON")
3. Play a short track: `play <short-track>`

**Expected:**
- ✅ Track plays to completion
- ✅ Next random track starts automatically
- ✅ No pause between tracks

**How to verify:**
- Watch the UI - track info should update automatically
- Listen for seamless transition

---

### Test 2: Sequential Mode with Active Playlist

**Setup:**
1. Start music-minion: `uv run music-minion`
2. Create test playlist: `playlist new manual test`
3. Add a few tracks (use `add test` while playing different songs)
4. Activate playlist: `playlist active test`
5. Enable sequential mode: `shuffle off`
6. Play first track: `play`

**Expected:**
- ✅ Track 1 plays to completion
- ✅ Track 2 starts automatically (in playlist order)
- ✅ Track 3 starts automatically
- ✅ Playlist loops back to track 1 after last track

**How to verify:**
- Watch position counter in UI: "Position: 1/3" → "Position: 2/3" → "Position: 3/3" → "Position: 1/3"
- Verify tracks play in same order as `playlist show test`

---

### Test 3: Shuffle with Active Playlist

**Setup:**
1. Keep playlist from Test 2 active: `playlist active test`
2. Enable shuffle: `shuffle on`
3. Play a track: `play`

**Expected:**
- ✅ Track plays to completion
- ✅ Next track is random (from playlist only)
- ✅ Never plays archived tracks

**How to verify:**
- Tracks should only be from the active playlist
- Order should be random

---

### Test 4: Handling Archived Tracks

**Setup:**
1. Play a track: `play`
2. Let it play most of the way
3. Archive it while playing: `archive`

**Expected:**
- ✅ Current track continues playing
- ✅ After completion, skips to next non-archived track
- ✅ Archived track won't repeat

---

### Test 5: Manual Skip vs Auto-Advance

**Setup:**
1. Play a track: `play`
2. Skip manually: `skip` (before track ends)
3. Let next track play to completion

**Expected:**
- ✅ Manual skip works immediately
- ✅ Auto-advance works after track ends
- ✅ Both respect shuffle/sequential settings

---

## Edge Cases to Test

### Edge 1: No Available Tracks
1. Archive all tracks in small playlist
2. Activate that playlist
3. Play a track

**Expected:** Stops after current track (no tracks available)

### Edge 2: Single Track Playlist (Sequential)
1. Create playlist with 1 track
2. Activate it, shuffle off
3. Play

**Expected:** Loops same track forever

### Edge 3: MPV Restart During Playback
1. Play a track
2. Kill MPV process manually: `pkill mpv`
3. Wait for detection

**Expected:** Graceful degradation (error handling)

---

## Performance Validation

**Metrics to watch:**
- ✅ No flashing/flickering during track transition
- ✅ UI updates smoothly (partial rendering works)
- ✅ No delay between tracks (< 0.5s gap)
- ✅ Database queries efficient (no lag)

---

## Rollback Plan

If issues occur:
```bash
git revert HEAD
```

Files modified:
- `src/music_minion/domain/playback/player.py` - Added `is_track_finished()`
- `src/music_minion/domain/playback/__init__.py` - Export new function
- `src/music_minion/commands/playback.py` - Extracted `get_next_track()`
- `src/music_minion/ui/blessed/app.py` - Auto-advance in `poll_player_state()`
