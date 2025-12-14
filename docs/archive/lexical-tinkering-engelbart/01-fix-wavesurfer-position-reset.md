# Fix useWavesurfer Position Reset

## Files to Modify
- `web/frontend/src/hooks/useWavesurfer.ts` (modify)

## Problem
The main effect (lines 156-181) resets `lastPositionRef.current = 0` whenever `initWavesurfer` changes - not just when the track changes. This causes position loss on pause/resume because callback changes trigger unnecessary reinitialization.

## Implementation Details

### Add ref to track previous trackId
Add near the top of the hook (after line 42):
```typescript
const prevTrackIdRef = useRef<number | null>(null);
```

### Modify the main effect (lines 156-181)
Replace the unconditional position reset with a conditional check:

**Current code (line 159-160):**
```typescript
// Reset resume position when track changes
lastPositionRef.current = 0;
```

**New code:**
```typescript
// Only reset position when track ACTUALLY changes, not on callback updates
const trackChanged = prevTrackIdRef.current !== trackId;
if (trackChanged) {
  lastPositionRef.current = 0;
  prevTrackIdRef.current = trackId;
}
```

The rest of the effect remains unchanged.

## Acceptance Criteria
- [ ] Position is NOT reset when `initWavesurfer` callback changes (due to parent re-renders)
- [ ] Position IS reset when `trackId` actually changes to a different track
- [ ] `prevTrackIdRef` is properly initialized and updated
- [ ] No TypeScript errors

## Dependencies
None - this is the first task.
