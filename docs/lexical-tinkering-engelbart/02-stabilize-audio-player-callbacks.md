# Stabilize useAudioPlayer Callbacks

## Files to Modify
- `web/frontend/src/hooks/useAudioPlayer.ts` (modify)

## Problem
`playTrack` and `pauseTrack` functions are NOT memoized, causing them to be recreated on every render. This triggers the callback cascade that destroys WaveSurfer.

## Implementation Details

### Add useCallback import
Update the import at line 1:
```typescript
import { useEffect, useCallback } from 'react';
```

### Memoize playTrack (around line 17-19)
**Current code:**
```typescript
const playTrack = (trackToPlay: TrackInfo) => {
  setPlaying(trackToPlay);
};
```

**New code:**
```typescript
const playTrack = useCallback((trackToPlay: TrackInfo) => {
  setPlaying(trackToPlay);
}, [setPlaying]);
```

### Memoize pauseTrack (around line 21-23)
**Current code:**
```typescript
const pauseTrack = () => {
  setPlaying(null);
};
```

**New code:**
```typescript
const pauseTrack = useCallback(() => {
  setPlaying(null);
}, [setPlaying]);
```

Note: `setPlaying` from Zustand is a stable reference, so these callbacks will remain stable across renders.

## Acceptance Criteria
- [ ] `playTrack` is memoized with `useCallback`
- [ ] `pauseTrack` is memoized with `useCallback`
- [ ] Dependencies array includes `[setPlaying]`
- [ ] No TypeScript errors
- [ ] Callbacks maintain stable identity across re-renders

## Dependencies
- Task 01 should be completed first (core fix)
