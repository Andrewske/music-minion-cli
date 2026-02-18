---
task: 02-manual-testing-verification
status: done
depends: [01-refactor-homepage-implementation]
files: []
---

# Manual Testing and Verification

## Context
Comprehensive testing of the refactored Home page to verify all functionality works correctly across different scenarios, devices, and edge cases. This includes testing all new features: playlist title display, queue position indicator, loop persistence, keyboard shortcuts, loading states, and click-to-seek.

## Implementation Details

This task involves no code changes - only testing and verification.

## Verification

### 1. Empty State Testing

**Steps:**
1. Clear any active playback
2. Navigate to Home (`/`)
3. Verify empty state shows "Nothing playing"
4. Verify station chips display below
5. Click a station chip
6. Verify loading spinner appears
7. Verify playback starts after ~500ms
8. Verify page transitions to playing state

**Expected results:**
- ✓ Empty state displays with Obsidian theme styling
- ✓ Station chips are visible and clickable
- ✓ Loading spinner shows during transition
- ✓ Playback starts smoothly
- ✓ No flash of empty state after loading

---

### 2. Playlist Title Display

**Steps:**
1. Start playback from a playlist (via sidebar)
2. Navigate to Home
3. Check header title

**Expected results:**
- ✓ Header shows actual playlist name (e.g., "Chill Vibes")
- ✓ Falls back to "Playlist #ID" if name not in cache
- ✓ Shows "Queue" if no context
- ✓ Shows "Search: query" for search results
- ✓ Shows "Builder" / "Comparison" / "Track" for other contexts

---

### 3. Queue Position Indicator

**Steps:**
1. With active playback, check header
2. Navigate through queue (click different tracks)
3. Verify indicator updates

**Expected results:**
- ✓ Shows "Track X of Y" next to playlist name
- ✓ Updates when clicking different tracks
- ✓ Correctly reflects current position in queue
- ✓ Hidden when queue is empty

---

### 4. Loop Persistence Testing

**Steps:**
1. Enable loop toggle on Home page
2. Refresh browser (F5)
3. Navigate away and back to Home
4. Close tab and reopen
5. Verify loop state persists
6. Disable loop
7. Refresh again
8. Verify loop stays disabled

**Expected results:**
- ✓ Loop toggle state persists across page refreshes
- ✓ Loop toggle state persists across navigation
- ✓ Loop toggle state persists across browser sessions
- ✓ Stored in localStorage as `music-minion-home-loop`

---

### 5. Spacebar Keyboard Shortcut

**Steps:**
1. With active playback, press Spacebar
2. Verify playback pauses
3. Press Spacebar again
4. Verify playback resumes
5. Click into search/filter input field (if exists)
6. Press Spacebar
7. Verify it types a space (doesn't toggle playback)
8. Click outside input, press Spacebar
9. Verify playback toggles again

**Expected results:**
- ✓ Spacebar toggles play/pause
- ✓ Works when not focused on input elements
- ✓ Does NOT trigger when typing in inputs/textareas
- ✓ Prevents default spacebar scroll behavior

---

### 6. Active Playback Testing

**Steps:**
1. Start playback from a playlist (via sidebar)
2. Navigate to Home
3. Verify all components render correctly

**Expected results:**
- ✓ TrackDisplay shows current track metadata (artist, title, album)
- ✓ Metadata pills visible (BPM, key, genre, year) if available
- ✓ WaveformSection shows waveform visualization
- ✓ Waveform plays/pauses on click
- ✓ TrackQueueTable shows full queue
- ✓ Current track highlighted with obsidian-accent border
- ✓ Virtual scrolling works for long queues

---

### 7. Waveform Controls Testing

**Steps:**
1. Click waveform to pause playback
2. Click again to resume
3. Click different positions on waveform to seek
4. Verify position updates correctly
5. Enable loop toggle
6. Let track play to completion
7. Verify it restarts
8. Disable loop toggle
9. Let track play to completion
10. Verify it advances to next track

**Expected results:**
- ✓ Waveform click toggles play/pause
- ✓ Click-to-seek works (verify with WaveformPlayer)
- ✓ Position updates smoothly
- ✓ Loop toggle enables/disables correctly
- ✓ With loop: track restarts on finish
- ✓ Without loop: auto-advances to next track

---

### 8. Queue Interaction Testing

**Steps:**
1. With active playback, scroll through queue table
2. Click a track 5-10 positions ahead in queue
3. Verify playback jumps to that track
4. Verify queue highlighting updates to new position
5. Verify "Track X of Y" indicator updates
6. Click another track in different position
7. Repeat verification

**Expected results:**
- ✓ Clicking any track in queue jumps to that position
- ✓ Queue highlighting updates correctly
- ✓ Queue position indicator updates
- ✓ Playback continues from new position
- ✓ Context is preserved (playlist/search/etc.)

---

### 9. Loading State Testing

**Steps:**
1. Stop playback
2. Click a station chip
3. Observe loading state
4. Verify spinner appears
5. Verify "Loading playback..." text shows
6. Wait for playback to start
7. Verify transition is smooth

**Expected results:**
- ✓ Loading spinner uses Obsidian accent color
- ✓ Loading text is visible and clear
- ✓ Spinner shows for at least 500ms (prevents flash)
- ✓ Smooth transition from loading → playing
- ✓ No empty state flash during transition

---

### 10. Empty Queue Edge Case

**Steps:**
1. Play a single track (if possible in current system)
2. Verify "No tracks in queue" message shows below player
3. Verify player controls still work
4. Verify no crashes or console errors

**Expected results:**
- ✓ "No tracks in queue" message displays
- ✓ Player controls remain functional
- ✓ No layout breaks or errors

---

### 11. Responsive Design Testing

**Desktop (>= 768px width):**
- ✓ Full table view with all columns visible
- ✓ Column headers show with sort indicators
- ✓ Virtual scrolling works smoothly
- ✓ Player section is NOT sticky
- ✓ Queue position indicator visible

**Mobile (< 768px width):**
- ✓ Card view instead of table
- ✓ Sort dropdown selector visible
- ✓ Player section is sticky at top
- ✓ Cards display all metadata clearly
- ✓ Spacebar shortcut works on mobile browsers

**Tablet (breakpoint transition):**
- ✓ Smooth transition between mobile and desktop views
- ✓ No layout jumps or flashing

---

### 12. Browser Compatibility Testing

Test in these browsers:
- Chrome/Chromium (primary)
- Firefox
- Safari (if available)

**Check:**
- ✓ Waveform renders correctly
- ✓ Virtual scrolling performs well
- ✓ Sticky positioning works on mobile
- ✓ Font rendering (Inter, SF Mono) looks correct
- ✓ localStorage persistence works
- ✓ Keyboard events work correctly

---

### 13. Edge Cases Testing

**Track without metadata:**
- ✓ Missing fields show as "-" or are omitted
- ✓ No console errors
- ✓ Layout remains consistent

**Very long queue (100+ tracks):**
- ✓ Virtual scrolling maintains performance
- ✓ No lag when scrolling
- ✓ Highlighting works even at end of queue
- ✓ Queue position indicator shows correct numbers

**Rapid navigation:**
- ✓ Clicking multiple tracks quickly doesn't break state
- ✓ Position indicator stays in sync
- ✓ No race conditions

**localStorage edge cases:**
- ✓ Works when localStorage is disabled (graceful fallback)
- ✓ Invalid JSON in storage doesn't crash (defaults to false)

---

## Success Criteria

All checkboxes above should be ✓ before considering the implementation complete.

**Critical paths that MUST work:**
1. Empty state → click station → loading → playback starts
2. Active playback → click queue track → jumps to track
3. Track finishes → auto-advances to next (when not looping)
4. Track finishes → restarts (when looping)
5. Spacebar → toggles play/pause
6. Refresh page → loop state persists
7. Click waveform → seeks to position
8. Queue position indicator → always accurate

**If any tests fail:**
1. Document the failure in detail
2. Return to task 01 to fix
3. Re-run verification

---

## Performance Benchmarks

Optional performance checks:

- Virtual scroll rendering: < 16ms per frame (60 FPS)
- Track click latency: < 200ms to start playback
- Queue highlighting update: < 100ms
- Empty → playing transition: < 500ms
- Waveform seek response: < 100ms
- Keyboard shortcut response: < 50ms

---

## Notes

- Test with both short (<20 tracks) and long (100+) queues
- Test with various track metadata completeness levels
- Test on actual mobile device if possible (not just browser DevTools)
- Check console for any warnings or errors during all tests
- Verify localStorage doesn't grow unbounded (should only store 1 boolean)
