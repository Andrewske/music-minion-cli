# Stabilize ComparisonView handleTrackFinish Callback

## Files to Modify
- `web/frontend/src/components/ComparisonView.tsx` (modify)

## Problem
`handleTrackFinish` depends on `playingTrack` in its dependency array. When `playingTrack` changes (including to null on pause), the callback is recreated, triggering the cascade that destroys WaveSurfer.

## Implementation Details

### Add useRef import
Ensure `useRef` is imported (should already be available, but verify):
```typescript
import { useCallback, useState, useEffect, useRef } from 'react';
```

### Add playingTrackRef (after line 50, near other useState calls)
```typescript
// Ref for playingTrack to avoid dependency in handleTrackFinish
const playingTrackRef = useRef(playingTrack);
useEffect(() => {
  playingTrackRef.current = playingTrack;
}, [playingTrack]);
```

### Update handleTrackFinish (lines 103-113)
**Current code:**
```typescript
const handleTrackFinish = useCallback(() => {
  if (!currentPair || !playingTrack || !isComparisonMode) return;

  const otherTrack = playingTrack.id === currentPair.track_a.id
    ? currentPair.track_b
    : currentPair.track_a;

  playTrack(otherTrack);
}, [currentPair, playingTrack, isComparisonMode, playTrack]);
```

**New code:**
```typescript
const handleTrackFinish = useCallback(() => {
  if (!currentPair || !playingTrackRef.current || !isComparisonMode) return;

  const otherTrack = playingTrackRef.current.id === currentPair.track_a.id
    ? currentPair.track_b
    : currentPair.track_a;

  playTrack(otherTrack);
}, [currentPair, isComparisonMode, playTrack]); // playingTrack removed from deps
```

## Acceptance Criteria
- [ ] `playingTrackRef` is created and kept in sync with `playingTrack`
- [ ] `handleTrackFinish` uses `playingTrackRef.current` instead of `playingTrack`
- [ ] `playingTrack` is removed from the dependency array
- [ ] Track auto-switch on finish still works correctly
- [ ] No TypeScript errors

## Dependencies
- Task 01 (core fix)
- Task 02 (stable `playTrack` callback)

## Testing Checklist
After all tasks complete:
- [ ] Pause via waveform play button, resume - position maintained
- [ ] Pause via track card tap, resume - position maintained
- [ ] Pause via IPC playpause command, resume - position maintained
- [ ] Switch between track A and track B - position resets (expected)
- [ ] Advance to next comparison pair - position resets (expected)
- [ ] Track finishes naturally - auto-switch to other track works
