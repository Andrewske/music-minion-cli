---
task: 05-frontend-review-mode-ui
status: done
depends: [04-frontend-hook-mutations]
files:
  - path: web/frontend/src/pages/SmartPlaylistEditor.tsx
    action: modify
---

# Frontend: Add Review Mode UI to SmartPlaylistEditor

## Context
The SmartPlaylistEditor needs a review mode where users can cycle through tracks one-at-a-time and skip individual tracks. This provides the same workflow as the manual playlist builder but for smart playlists.

## Files to Modify/Create
- web/frontend/src/pages/SmartPlaylistEditor.tsx (modify)

## Implementation Details

1. **Mode toggle button:**
   - Add "Review Mode" / "Filter Mode" toggle in the header area
   - When clicked, toggle `isReviewMode` state from hook

2. **Review mode view (when isReviewMode is true):**
   - Hide the FilterPanel and track table
   - Show:
     - `WaveformPlayer` component (reuse from PlaylistBuilder)
     - Track metadata: title, artist, BPM, key, genre, year, emojis
     - Progress indicator: "Track {currentTrackIndex + 1} of {tracks.length}"
     - **Skip button**: calls `skipTrack.mutate(currentTrack.id)` - on success, advances to next track automatically (currentTrackId stays same, but that track is now removed from array, so we're pointing at what was the next track)
     - **Keep button**: calls `nextTrack()` (no database change)
     - Previous/Next navigation arrows (Previous wraps to end at index 0)

   **Edge cases:**
   - If skipping last track: show "All tracks reviewed" completion state, then exit review mode
   - If tracks.length === 0: show empty state ("No tracks to review") or auto-exit review mode
   - Disable "Review Mode" button when tracks.length === 0

3. **Filter mode view (when isReviewMode is false):**
   - Current behavior unchanged: FilterPanel + track table
   - Add "View Skipped ({count})" button that opens SkippedTracksDialog

4. **Component reuse:**
   - Import and use existing `WaveformPlayer` (already imported in SmartPlaylistEditor)
   - `SkippedTracksDialog` will be created in Task 06
   - Style consistently with PlaylistBuilder

## Verification
1. Open a smart playlist
2. Click "Review Mode" - verify waveform player and track info appear
3. Click Skip - verify track is excluded and advances to next
4. Click Keep - verify advances without skipping
5. Click "Filter Mode" - verify returns to filter/table view
6. Click "View Skipped" - verify dialog shows skipped tracks
