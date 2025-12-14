# Update Audio Hooks

## Files to Modify
- `web/frontend/src/hooks/useAudioPlayer.ts` (modify)
- `web/frontend/src/hooks/useIPCWebSocket.ts` (modify)

## Implementation Details

### useAudioPlayer.ts

Update to use the new store shape:

```typescript
import { useCallback } from 'react';
import { useComparisonStore } from '../stores/comparisonStore';
import type { TrackInfo } from '../types';

export function useAudioPlayer(track: TrackInfo | null, isComparisonMode = false) {
  const { currentTrack, isPlaying, setIsPlaying, selectAndPlay } = useComparisonStore();

  const playTrack = useCallback((trackToPlay: TrackInfo) => {
    selectAndPlay(trackToPlay);
  }, [selectAndPlay]);

  const pauseTrack = useCallback(() => {
    setIsPlaying(false);
  }, [setIsPlaying]);

  const isTrackPlaying = isPlaying && currentTrack?.id === track?.id;

  return {
    isPlaying: isTrackPlaying,
    playTrack,
    pauseTrack,
  };
}
```

### useIPCWebSocket.ts

Simplify IPC command handlers to use the new actions:

```typescript
// Get togglePlaying and selectAndPlay from store
const { currentPair, togglePlaying, selectAndPlay } = useComparisonStore();

// In message handler switch:
case 'playpause':
  togglePlaying();  // Simple toggle, remembers current track
  break;

case 'play1':
  if (currentPair) selectAndPlay(currentPair.track_a);
  break;

case 'play2':
  if (currentPair) selectAndPlay(currentPair.track_b);
  break;
```

Key changes:
- Remove manual logic that checked `playingTrack` and set it to `null` or `track_a`
- Use `togglePlaying()` which handles the null-track edge case internally
- Use `selectAndPlay()` for explicit track selection

## Acceptance Criteria
- [ ] `useAudioPlayer` returns correct `isPlaying` based on both `currentTrack` match AND `isPlaying` state
- [ ] `pauseTrack` only sets `isPlaying: false` (doesn't clear track)
- [ ] `playTrack` calls `selectAndPlay` (sets track AND plays)
- [ ] IPC `playpause` uses `togglePlaying()`
- [ ] IPC `play1`/`play2` use `selectAndPlay()`
- [ ] Pausing track B then pressing playpause resumes track B (not track A)

## Dependencies
- Task 01 (store refactor must be complete)
