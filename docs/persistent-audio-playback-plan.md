# Persistent Audio Playback Across Comparisons - Implementation Plan

## Overview
Enable audio playback to persist independently of comparison submissions and track pair changes. The ONLY way to change what's playing is by explicitly clicking a track card or pressing pause.

## Architecture Decisions

### Persistent WaveformPlayer Approach
- **Choice**: Leverage existing architecture where WaveformPlayer is in a persistent bottom bar
- **Rationale**: The WaveformPlayer component (`ComparisonView.tsx:178-214`) is already rendered outside of the TrackCard components. It doesn't unmount when comparisons change. The `waveformTrackId` state only updates when `playingTrackId` changes to a non-null value, keeping the player stable.

### Store Full Track Object
- **Choice**: Store `playingTrack: Track | null` instead of just `playingTrackId: number | null`
- **Rationale**: When the playing track is not in the current pair, we still need its metadata (artist, title) for the player bar display. Storing the full object provides this without additional lookups.

### Remove Automatic Stop on Comparison
- **Choice**: Delete the `setPlaying(null)` call from comparison submission
- **Rationale**: This was the only code stopping playback on comparison. Removing it lets audio continue. The existing WaveSurfer instance keeps playing because its `trackId` prop doesn't change.

## Implementation Tasks

### Phase 1: Store Enhancement
- [x] Replace `playingTrackId` with `playingTrack` in comparison store
  - Files: `web/frontend/src/stores/comparisonStore.ts`
  - Changes:
    - Replace `playingTrackId: number | null` with `playingTrack: Track | null`
    - Update `setPlaying` signature to `setPlaying: (track: Track | null) => void`
    - Update initial state and reset function
  - Acceptance: TypeScript compiles without errors

### Phase 2: Remove Automatic Playback Stop
- [x] Remove `setPlaying(null)` call from comparison submission handler
  - Files: `web/frontend/src/hooks/useComparison.ts` (line 31)
  - Remove the line: `setPlaying(null);`
  - Acceptance: Comparison submission no longer affects playback state

### Phase 3: Update Consumers
- [x] Update useAudioPlayer hook
  - Files: `web/frontend/src/hooks/useAudioPlayer.ts`
  - Changes:
    - `playTrack` now accepts full `Track` object
    - `isPlaying` check uses `playingTrack?.id`
  - Acceptance: Hook API updated, TypeScript compiles

- [x] Update ComparisonView
  - Files: `web/frontend/src/components/ComparisonView.tsx`
  - Changes:
    - Update `handleTrackTap` to pass full track object
    - Update player bar display to use `playingTrack?.artist` and `playingTrack?.title` directly (not derived from `currentPair`)
    - Replace `waveformTrackId` with `playingTrack?.id` where applicable
  - Acceptance: Player bar shows correct track info even when track not in current pair

## Test Scenarios

### Manual Testing Checklist
- [x] **Same track in next pair**: Play Track A, submit comparison, verify Track A continues if in next pair
- [x] **Track not in next pair**: Play Track A, submit comparison, verify Track A continues even if NOT in next pair (and displays correct info)
- [x] **Explicit switching**: While Track A plays, click Track B, verify switch happens cleanly
- [x] **Pause/resume**: Pause track, submit comparison, verify paused state persists, resume works
- [x] **No playback active**: Submit comparison without playing, verify no audio starts
- [x] **Multiple rapid comparisons**: Play Track A, submit 5 comparisons rapidly, verify Track A plays throughout
- [x] **Archive while playing**: Archive a different track while one is playing, verify playback unaffected

## Acceptance Criteria
- No TypeScript compilation errors
- Audio playback persists across comparison submissions
- Only user-initiated track clicks or pause button change playback
- Player bar shows correct track info regardless of current pair
- No audio glitches or interruptions during transitions

## Files to Modify

1. `web/frontend/src/stores/comparisonStore.ts`
   - Replace `playingTrackId: number | null` with `playingTrack: Track | null`
   - Update `setPlaying` to accept `Track | null`

2. `web/frontend/src/hooks/useComparison.ts`
   - Remove `setPlaying(null)` from line 31

3. `web/frontend/src/hooks/useAudioPlayer.ts`
   - Update to use `playingTrack` instead of `playingTrackId`
   - `playTrack` accepts `Track` object

4. `web/frontend/src/components/ComparisonView.tsx`
   - Pass full track to `playTrack`
   - Use `playingTrack` for player bar display

## Why This Works

The key insight is that the WaveformPlayer is already persistent:
1. It lives in `ComparisonView.tsx:178-214`, outside the TrackCard components
2. Its `trackId` prop comes from `waveformTrackId` state
3. `waveformTrackId` only updates when `playingTrackId` changes to a non-null value
4. When we remove `setPlaying(null)`, `playingTrackId` stays stable across comparisons
5. Therefore `waveformTrackId` stays stable, and the WaveformPlayer keeps the same `trackId`
6. The WaveSurfer instance is never destroyed, audio continues uninterrupted

No MediaElement extraction needed. No background audio management. Just stop resetting the state.

## Rollback Plan
If issues arise:
1. Revert `useComparison.ts` to restore `setPlaying(null)` call
2. Revert store to use `playingTrackId: number | null`
3. Revert consumer updates
4. System returns to previous behavior (playback stops on comparison)

## Future Enhancements (Not in Scope)
- Visual indicator showing which track card is currently playing (when track is in current pair)
- Media session API integration for lock screen controls
