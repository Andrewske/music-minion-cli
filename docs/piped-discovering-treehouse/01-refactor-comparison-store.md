# Refactor Comparison Store State

## Files to Modify
- `web/frontend/src/stores/comparisonStore.ts` (modify)

## Implementation Details

Replace the conflated `playingTrack` field with two separate fields:
- `currentTrack: TrackInfo | null` - which track is loaded/selected
- `isPlaying: boolean` - whether audio is currently playing

### State Changes

**Before:**
```typescript
interface ComparisonState {
  playingTrack: TrackInfo | null;
  // ...
}
```

**After:**
```typescript
interface ComparisonState {
  currentTrack: TrackInfo | null;  // Which track is loaded/selected
  isPlaying: boolean;              // Is audio currently playing
  // ...
}
```

### New Actions

Add to `ComparisonActions`:
```typescript
interface ComparisonActions {
  setCurrentTrack: (track: TrackInfo | null) => void;
  setIsPlaying: (playing: boolean) => void;
  togglePlaying: () => void;
  selectAndPlay: (track: TrackInfo) => void;  // For track switch
}
```

### Updated Action Implementations

```typescript
setSession: (sessionId, pair, prefetched, priorityPathPrefix) => {
  set({
    sessionId,
    currentPair: pair,
    prefetchedPair: prefetched ?? null,
    currentTrack: pair.track_a,  // Load track A
    isPlaying: false,            // But don't play yet
    comparisonsCompleted: 0,
    priorityPathPrefix: priorityPathPrefix ?? null,
    isComparisonMode: true,
  });
},

advanceToNextPair: (nextPair, prefetched) => {
  set({
    currentPair: nextPair,
    prefetchedPair: prefetched ?? null,
    currentTrack: nextPair.track_a,  // Load track A
    isPlaying: false,                // Wait for user action
    isComparisonMode: true,
  });
},

togglePlaying: () => {
  const { isPlaying, currentTrack, currentPair } = get();
  if (!currentTrack && currentPair) {
    // No track loaded, load track A and play
    set({ currentTrack: currentPair.track_a, isPlaying: true });
  } else {
    set({ isPlaying: !isPlaying });
  }
},

selectAndPlay: (track) => {
  set({ currentTrack: track, isPlaying: true });
},

setCurrentTrack: (track) => {
  set({ currentTrack: track });
},

setIsPlaying: (playing) => {
  set({ isPlaying: playing });
},
```

### Remove
- Remove `setPlaying` action (replaced by `setIsPlaying`, `togglePlaying`, `selectAndPlay`)
- Remove `playingTrack` from state and initial state

## Acceptance Criteria
- [ ] `playingTrack` field removed from state
- [ ] `currentTrack` and `isPlaying` fields added
- [ ] All new actions implemented
- [ ] Initial state sets `isPlaying: false`
- [ ] `setSession` loads track A but doesn't auto-play
- [ ] `advanceToNextPair` loads track A but doesn't auto-play
- [ ] TypeScript compiles (other files will break - that's expected)

## Dependencies
None - this is the foundational change
