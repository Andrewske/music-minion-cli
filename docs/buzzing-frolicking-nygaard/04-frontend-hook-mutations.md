---
task: 04-frontend-hook-mutations
status: done
depends: [03-frontend-api-functions]
files:
  - path: web/frontend/src/hooks/useSmartPlaylistEditor.ts
    action: modify
---

# Frontend: Add Skip Mutations to useSmartPlaylistEditor Hook

## Context
The useSmartPlaylistEditor hook needs mutations for skip/unskip operations and state for review mode navigation. This prepares the data layer before adding the UI.

## Files to Modify/Create
- web/frontend/src/hooks/useSmartPlaylistEditor.ts (modify)

## Implementation Details
Add to the hook:

1. **Queries:**
   - `skippedTracks` query using `getSmartPlaylistSkippedTracks()`
   - Query key: `['smart-playlist-skipped', playlistId]`

2. **Mutations:**
   - `skipTrack` mutation using `skipSmartPlaylistTrack()`
     - On success: invalidate `['playlist-tracks', playlistId]` and `['smart-playlist-skipped', playlistId]`
   - `unskipTrack` mutation using `unskipSmartPlaylistTrack()`
     - On success: invalidate same queries

3. **Review mode state:**
   - `currentTrackId: number | null` - ID of current track (source of truth)
   - `currentTrackIndex: number` - derived from finding currentTrackId in tracks array
   - `isReviewMode: boolean` - toggle between filter view and review view
   - `nextTrack()` - set currentTrackId to next track's ID
   - `previousTrack()` - set currentTrackId to previous track's ID (wraps to end at index 0)
   - `currentTrack` - derived from tracks.find(t => t.id === currentTrackId)

   **Edge case handling:**
   - Skip last track → show "All tracks reviewed" completion state, exit review mode
   - 0 tracks → disable review mode button
   - previousTrack() at index 0 → wrap to last track (allows re-listening)

4. **Return values:**
   Add to hook return: `skipTrack`, `unskipTrack`, `skippedTracks`, `currentTrack`, `currentTrackIndex`, `nextTrack`, `previousTrack`, `isReviewMode`, `setIsReviewMode`

## Verification
1. Use hook in a test component
2. Call `skipTrack.mutate(trackId)` - verify track disappears from tracks list
3. Check `skippedTracks` query returns the skipped track
4. Call `unskipTrack.mutate(trackId)` - verify track reappears
5. Test `nextTrack()`/`previousTrack()` navigation
