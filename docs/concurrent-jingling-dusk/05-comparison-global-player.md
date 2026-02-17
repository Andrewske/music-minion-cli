---
task: 05-comparison-global-player
status: pending
depends: [02-integrate-useplayer, 03-wavesurfer-external-audio]
files:
  - path: web/frontend/src/components/ComparisonView.tsx
    action: modify
  - path: web/frontend/src/stores/comparisonStore.ts
    action: modify
  - path: web/frontend/src/hooks/usePlayer.ts
    action: modify
  - path: web/frontend/src/hooks/useAudioPlayer.ts
    action: delete
---

# ComparisonView Global Player Integration

## Context
ComparisonView uses a separate comparisonStore for playback state. This task moves playback to the global player while keeping session/pair state in comparisonStore. A/B looping must be preserved.

## Files to Modify/Create
- web/frontend/src/components/ComparisonView.tsx (modify)
- web/frontend/src/stores/comparisonStore.ts (modify)
- web/frontend/src/hooks/usePlayer.ts (modify)
- web/frontend/src/hooks/useAudioPlayer.ts (delete)

## Implementation Details

### 1. Simplify comparisonStore.ts

**REMOVE playback state and actions:**
```typescript
// DELETE from state interface
currentTrack: TrackInfo | null;
isPlaying: boolean;

// DELETE these actions
setCurrentTrack: (track: TrackInfo | null) => void;
setIsPlaying: (playing: boolean) => void;
togglePlaying: () => void;
selectAndPlay: (track: TrackInfo) => void;
```

**KEEP session state:**
```typescript
// KEEP these
sessionId: string | null;
currentPair: ComparisonPair | null;
prefetchedPair: ComparisonPair | null;
comparisonsCompleted: number;
autoplay: boolean;
rankingMode: 'global' | 'playlist' | null;
priorityPathPrefix: string | null;
isComparisonMode: boolean;
```

### 2. Update ComparisonView.tsx

**REPLACE store usage:**
```typescript
// BEFORE
const { currentTrack, isPlaying, selectAndPlay } = useComparisonStore();

// AFTER
import { usePlayerStore } from '../stores/playerStore';

const { currentTrack, isPlaying, play, pause, resume } = usePlayerStore();
const { currentPair, sessionId, comparisonsCompleted } = useComparisonStore();
```

**UPDATE track tap handler:**
```typescript
const handleTrackTap = (track: TrackInfo) => {
  if (currentTrack?.id === track.id) {
    isPlaying ? pause() : resume();
  } else {
    play(track, { type: 'comparison' });
  }
};
```

**UPDATE A/B looping (onFinish callback):**
```typescript
const { isComparisonMode } = useComparisonStore();

const handleTrackFinish = useCallback(() => {
  // Guard: only do A/B switching if still in comparison mode
  // (user may have navigated away while track was playing)
  if (!currentPair || !currentTrack || !isComparisonMode) return;

  const otherTrack = currentTrack.id === currentPair.track_a.id
    ? currentPair.track_b
    : currentPair.track_a;

  play(otherTrack, { type: 'comparison' });
}, [currentPair, currentTrack, isComparisonMode, play]);
```

### 3. Modify usePlayer.ts for comparison context

**ADD context tracking to playerStore** (if not already present):
The store needs to track current context type.

**MODIFY onEnded handler:**
```typescript
const onEnded = () => {
  // Comparison mode handles A/B switching via onFinish callback
  // Don't auto-advance queue
  if (store.currentContext?.type === 'comparison') return;
  store.next();
};
```

### 4. Delete useAudioPlayer.ts

This hook is now redundant - components use playerStore directly.

```bash
rm web/frontend/src/hooks/useAudioPlayer.ts
rm web/frontend/src/hooks/useAudioPlayer.test.ts
```

**Files that import useAudioPlayer (must update):**
- `web/frontend/src/components/ComparisonView.tsx` - remove import, use playerStore directly
- `web/frontend/src/components/ComparisonView.test.tsx` - update test mocks

## Verification
- Tap track in comparison → plays via global player
- A/B looping works (track A ends → track B plays → track A plays)
- Comparison session state (pair, completed count) preserved
- Only one audio plays at a time
- PlayerBar shows comparison track
