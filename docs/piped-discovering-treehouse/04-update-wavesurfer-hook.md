# Update WaveSurfer Hook

## Files to Modify
- `web/frontend/src/hooks/useWavesurfer.ts` (modify)

## Implementation Details

Update to accept explicit `isPlaying` prop instead of deriving from `isActive`:

### Interface Changes

```typescript
interface UseWavesurferOptions {
  trackId: number;
  audioUrl: string;
  isPlaying: boolean;  // NEW: Explicit control instead of isActive
  onFinish?: () => void;
  onReady?: (duration: number) => void;
  onTimeUpdate?: (currentTime: number) => void;
  startPosition?: number;
  endPosition?: number;
  // Remove isActive if it existed
}
```

### Effect for Play/Pause Control

Replace the existing `isActive` effect with one that responds to `isPlaying`:

```typescript
// Effect responds to isPlaying changes
useEffect(() => {
  if (!wavesurferRef.current) return;

  if (isPlaying && !wavesurferRef.current.isPlaying()) {
    wavesurferRef.current.play().catch((err) => {
      console.warn('Play failed:', err);
    });
  } else if (!isPlaying && wavesurferRef.current.isPlaying()) {
    wavesurferRef.current.pause();
  }
}, [isPlaying]);
```

### Remove Position Restoration Logic

The old implementation tried to restore position when `isActive` became true. Since we now use `isPlaying` directly:

- The position is maintained by WaveSurfer internally when paused
- No need for `lastPositionRef` for pause/resume (only for track switching)
- Simplify the logic

### Keep Track Change Detection

Still detect track ID changes to reset position:

```typescript
const prevTrackIdRef = useRef(trackId);

useEffect(() => {
  const trackChanged = prevTrackIdRef.current !== trackId;
  if (trackChanged) {
    lastPositionRef.current = 0;  // Reset position for new track
    prevTrackIdRef.current = trackId;
  }
}, [trackId]);
```

### Initial Load Behavior

On ready, only autoplay if `isPlaying` is true:

```typescript
wavesurfer.on('ready', () => {
  handleReady(wavesurfer.getDuration());
  if (isPlaying) {
    wavesurfer.play().catch(() => {});
  }
});
```

## Acceptance Criteria
- [ ] Hook accepts `isPlaying` prop directly
- [ ] Setting `isPlaying: true` starts playback
- [ ] Setting `isPlaying: false` pauses playback
- [ ] Pause preserves position (no restart on resume)
- [ ] Track change resets position to 0
- [ ] Initial load doesn't auto-play if `isPlaying: false`
- [ ] No `isActive` prop or derived state

## Dependencies
- Task 03 (WaveformPlayer passes isPlaying prop)
