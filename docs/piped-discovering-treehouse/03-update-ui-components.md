# Update UI Components

## Files to Modify
- `web/frontend/src/components/ComparisonView.tsx` (modify)
- `web/frontend/src/components/WaveformPlayer.tsx` (modify)

## Implementation Details

### ComparisonView.tsx

Remove `waveformTrack` local state - use `currentTrack` from store directly:

```typescript
// Before: had local waveformTrack state that was "sticky" on pause
// After: use currentTrack directly from store

const {
  currentTrack,
  isPlaying,
  currentPair,
  selectAndPlay,
  setIsPlaying
} = useComparisonStore();

// Remove this useEffect that managed waveformTrack:
// useEffect(() => {
//   if (playingTrack !== null) {
//     setWaveformTrack(playingTrack);
//   }
// }, [playingTrack]);

// Updated tap handler:
const handleTrackTap = (track: TrackInfo) => {
  if (currentTrack?.id === track.id) {
    setIsPlaying(!isPlaying);  // Toggle play/pause for same track
  } else {
    selectAndPlay(track);       // Switch track and play
  }
};

// Pass isPlaying to WaveformPlayer:
<WaveformPlayer
  track={currentTrack}
  isPlaying={isPlaying && currentTrack?.id === track.id}
  onTogglePlayPause={() => handleTrackTap(currentTrack)}
  // ...
/>
```

Key changes:
- Remove `waveformTrack` useState
- Remove the useEffect that updated `waveformTrack`
- Use `currentTrack` from store for waveform display
- Pass explicit `isPlaying` prop to WaveformPlayer

### WaveformPlayer.tsx

Accept explicit `isPlaying` prop:

```typescript
interface WaveformPlayerProps {
  track: TrackInfo;
  isPlaying: boolean;  // Explicit control from parent
  onTogglePlayPause?: () => void;
  // ... other props
}

export function WaveformPlayer({
  track,
  isPlaying,
  onTogglePlayPause,
  // ...
}: WaveformPlayerProps) {
  // Pass isPlaying to useWavesurfer
  const { /* ... */ } = useWavesurfer({
    trackId: track.id,
    audioUrl: track.audio_url,
    isPlaying,  // Pass through
    // ...
  });

  // ...
}
```

## Acceptance Criteria
- [ ] `waveformTrack` local state removed from ComparisonView
- [ ] ComparisonView uses `currentTrack` from store directly
- [ ] Track tap on same track toggles play/pause
- [ ] Track tap on different track switches and plays
- [ ] WaveformPlayer accepts `isPlaying` as explicit prop
- [ ] Waveform displays correctly when paused (shows currentTrack)
- [ ] Waveform shows correct track after pause/resume cycle

## Dependencies
- Task 01 (store refactor)
- Task 02 (hook updates)
