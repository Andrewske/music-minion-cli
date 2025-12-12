# Web UI Comparison Looping Playback Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement automatic looping playback between the two tracks being compared in the web UI, matching the CLI behavior where tracks automatically switch when one finishes.

**Architecture:** Add a 'finish' event handler to the WaveSurfer player that detects when a comparison track ends and automatically starts playing the other track in the pair. This maintains the comparison context until the user explicitly selects a winner or manually changes tracks.

**Tech Stack:** React, TypeScript, WaveSurfer.js, Zustand state management

## Implementation Overview

The web UI currently plays tracks individually without looping. We need to:

1. Detect when a track finishes playing in comparison mode
2. Automatically switch to the other track in the comparison pair
3. Continue looping until user intervention (winner selection or manual track change)
4. Preserve existing pause/play behavior

### Key Components to Modify

- `useWavesurfer.ts`: Add finish event handler for comparison looping
- `comparisonStore.ts`: Add state to track comparison mode and prevent manual interruptions
- `ComparisonView.tsx`: Wire up comparison context to audio player

---

### Task 1: Add Comparison Mode State to Store

**Files:**
- Modify: `web/frontend/src/stores/comparisonStore.ts`

**Step 1: Add comparison mode flag to store**

Add a boolean flag to track when we're in comparison mode to prevent conflicts with other playback modes.

```typescript
interface ComparisonState {
  // ... existing fields
  isComparisonMode: boolean;
}
```

**Step 2: Initialize comparison mode in setSession**

```typescript
setSession: (sessionId, pair, prefetched, priorityPathPrefix) => {
  set({
    sessionId,
    currentPair: pair,
    prefetchedPair: prefetched ?? null,
    comparisonsCompleted: 0,
    playingTrack: null,
    priorityPathPrefix: priorityPathPrefix ?? null,
    isComparisonMode: true, // Add this
  });
},
```

**Step 3: Reset comparison mode when advancing pairs**

```typescript
advanceToNextPair: (nextPair: ComparisonPair, prefetched?: ComparisonPair) => {
  set({
    currentPair: nextPair,
    prefetchedPair: prefetched ?? null,
    playingTrack: null, // Reset playing when switching pairs
    isComparisonMode: true, // Keep comparison mode active
  });
},
```

**Step 4: Reset comparison mode on session reset**

```typescript
reset: () => {
  set({
    ...initialState,
    isComparisonMode: false, // Reset to false
  });
},
```

---

### Task 2: Add Finish Event Handler to WaveSurfer Hook

**Files:**
- Modify: `web/frontend/src/hooks/useWavesurfer.ts`

**Step 1: Add onFinish callback to hook options**

```typescript
interface UseWavesurferOptions {
  trackId: number;
  onReady?: (duration: number) => void;
  onSeek?: (progress: number) => void;
  isActive?: boolean;
  onFinish?: () => void; // Add this
}
```

**Step 2: Update hook parameters and pass onFinish**

```typescript
export function useWavesurfer({ trackId, onReady, onSeek, isActive = false, onFinish }: UseWavesurferOptions) {
```

**Step 3: Wire up finish event in WaveSurfer setup**

```typescript
wavesurfer.on('finish', () => {
  setIsPlaying(false);
  onFinish?.(); // Call the finish callback
});
```

---

### Task 3: Implement Comparison Looping Logic in ComparisonView

**Files:**
- Modify: `web/frontend/src/components/ComparisonView.tsx`

**Step 1: Add comparison mode check to component**

```typescript
const { currentPair, playingTrack, comparisonsCompleted, priorityPathPrefix, setPriorityPath, isComparisonMode } = useComparisonStore();
```

**Step 2: Create finish handler function**

```typescript
const handleTrackFinish = useCallback(() => {
  if (!currentPair || !playingTrack || !isComparisonMode) return;

  // Determine which track just finished and play the other one
  const otherTrack = playingTrack.id === currentPair.track_a.id
    ? currentPair.track_b
    : currentPair.track_a;

  // Automatically play the other track
  playTrack(otherTrack);
}, [currentPair, playingTrack, isComparisonMode, playTrack]);
```

**Step 3: Pass finish handler to WaveformPlayer**

```typescript
<WaveformPlayer
  trackId={waveformTrack.id}
  onSeek={handleWaveformSeek}
  isActive={playingTrack?.id === waveformTrack.id}
  onTogglePlayPause={() => handleTrackTap(waveformTrack)}
  onFinish={handleTrackFinish} // Add this
/>
```

---

### Task 4: Add Debouncing to Prevent Rapid Loops

**Files:**
- Modify: `web/frontend/src/hooks/useWavesurfer.ts`

**Step 1: Add debouncing state to prevent rapid finish triggers**

```typescript
const [lastFinishTime, setLastFinishTime] = useState<number>(0);
```

**Step 2: Add debouncing logic to finish handler**

```typescript
wavesurfer.on('finish', () => {
  setIsPlaying(false);

  // Debounce finish events to prevent rapid looping
  const now = Date.now();
  if (now - lastFinishTime < 2000) { // 2 second cooldown
    return;
  }
  setLastFinishTime(now);

  onFinish?.();
});
```

---

### Task 5: Update Audio Player Hook for Comparison Context

**Files:**
- Modify: `web/frontend/src/hooks/useAudioPlayer.ts`

**Step 1: Add comparison mode awareness**

```typescript
export function useAudioPlayer(track: TrackInfo | null, isComparisonMode = false) {
```

**Step 2: Prevent automatic pausing when comparison mode is active**

```typescript
useEffect(() => {
  // If this track is playing and another track starts playing, pause this one
  // But skip this in comparison mode to allow seamless switching
  if (!isComparisonMode && playingTrack !== null && playingTrack.id !== track?.id) {
    // The WaveformPlayer component will handle pausing its own instance
  }
}, [playingTrack, track, isComparisonMode]);
```

**Step 3: Update ComparisonView to pass comparison mode**

```typescript
const { playTrack, pauseTrack } = useAudioPlayer(playingTrack, isComparisonMode);
```

---

### Task 6: Add Tests for Comparison Looping Behavior

**Files:**
- Create: `web/frontend/src/hooks/useWavesurfer.test.ts`
- Modify: `web/frontend/src/components/ComparisonView.test.tsx`

**Step 1: Test finish event triggers callback**

```typescript
describe('useWavesurfer finish event', () => {
  it('calls onFinish when track ends', async () => {
    const onFinish = jest.fn();
    const { result } = renderHook(() =>
      useWavesurfer({ trackId: 1, onFinish })
    );

    // Simulate track finishing
    // (Mock WaveSurfer finish event)

    expect(onFinish).toHaveBeenCalled();
  });
});
```

**Step 2: Test comparison mode prevents pausing**

```typescript
describe('useAudioPlayer in comparison mode', () => {
  it('does not pause when another track starts in comparison mode', () => {
    // Test that comparison mode allows seamless switching
  });
});
```

---

### Task 7: Update Type Definitions

**Files:**
- Modify: `web/frontend/src/types/index.ts`

**Step 1: Add onFinish to WaveformPlayer props**

```typescript
export interface WaveformPlayerProps {
  trackId: number;
  onSeek?: (progress: number) => void;
  isActive?: boolean;
  onTogglePlayPause?: () => void;
  onFinish?: () => void; // Add this
}
```

---

### Task 8: Add Documentation Comments

**Files:**
- Modify: `web/frontend/src/hooks/useWavesurfer.ts`
- Modify: `web/frontend/src/components/ComparisonView.tsx`

**Step 1: Document comparison looping behavior**

```typescript
/**
 * Handles automatic track switching in comparison mode.
 * When a track finishes playing, automatically starts the other track
 * in the comparison pair, creating a seamless looping experience.
 */
const handleTrackFinish = useCallback(() => {
  // ... implementation
}, [currentPair, playingTrack, isComparisonMode, playTrack]);
```

---

### Task 9: Test Integration and Edge Cases

**Files:**
- Run: Manual testing in browser

**Step 1: Test basic looping behavior**

1. Start comparison session
2. Play track A - verify it plays to completion
3. Verify track B automatically starts when A finishes
4. Verify track A starts when B finishes
5. Verify loop continues until winner selected

**Step 2: Test edge cases**

1. Pause during playback - verify looping resumes when unpaused
2. Manual track switching - verify it overrides automatic switching
3. Winner selection - verify looping stops
4. Session advancement - verify looping resets for new pair

**Step 3: Test performance**

1. Verify no memory leaks with repeated looping
2. Verify smooth transitions between tracks
3. Test with different track lengths

---

### Task 10: Final Verification and Cleanup

**Files:**
- Run: `npm run test` in web/frontend
- Run: `npm run lint` in web/frontend

**Step 1: Run all tests**

```bash
cd web/frontend
npm run test
```

**Step 2: Run linting**

```bash
cd web/frontend
npm run lint
```

**Step 3: Manual verification**

Test the complete flow in browser to ensure looping works as expected.

---

## Verification Steps

1. **Unit Tests**: All new tests pass
2. **Integration Tests**: Comparison session works end-to-end
3. **Manual Testing**: Looping behavior matches CLI implementation
4. **Performance**: No memory leaks or performance issues
5. **Edge Cases**: All edge cases handled correctly

## Rollback Plan

If issues arise, the changes are isolated to:
- Comparison store state additions
- WaveSurfer finish event handling
- ComparisonView finish logic

Can rollback by reverting these specific changes without affecting other playback functionality.