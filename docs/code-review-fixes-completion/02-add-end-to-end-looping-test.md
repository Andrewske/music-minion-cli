# Add End-to-End Looping Test

## Files to Modify/Create
- `web/frontend/src/components/ComparisonView.test.tsx` (modify)

## Implementation Details

Add a comprehensive integration test that verifies the complete looping cycle: track A finishes → track B plays → track B finishes → track A plays.

### Location
Add test at end of `handleTrackFinish` describe block (around line 330)

### Test Implementation

```typescript
it('completes full loop cycle: track A finishes → track B plays → track B finishes → track A plays', () => {
  const mockPlayTrack = vi.fn();
  const capturedCallbacks: Record<number, () => void> = {};

  // Mock WaveformPlayer to capture onFinish for different tracks
  vi.mocked(WaveformPlayer).mockImplementation((props: any) => {
    if (props.onFinish) {
      capturedCallbacks[props.trackId] = props.onFinish;
    }
    return null;
  });

  mockUseAudioPlayer.mockReturnValue({
    playTrack: mockPlayTrack,
    pauseTrack: vi.fn(),
  });

  // Start with track A playing
  mockUseComparisonStore.mockReturnValue({
    currentPair: {
      session_id: 1,
      track_a: mockTrackA,
      track_b: mockTrackB,
    },
    playingTrack: mockTrackA,
    comparisonsCompleted: 5,
    isComparisonMode: true,
    sessionId: '1',
    prefetchedPair: null,
    priorityPathPrefix: null,
    setSession: vi.fn(),
    setPlaying: vi.fn(),
    incrementCompleted: vi.fn(),
    reset: vi.fn(),
    setCurrentPair: vi.fn(),
    advanceToNextPair: vi.fn(),
    setPriorityPath: vi.fn(),
  });

  const { rerender } = renderComponent();

  // Step 1: Track A finishes → should switch to track B
  expect(capturedCallbacks[mockTrackA.id]).toBeDefined();
  capturedCallbacks[mockTrackA.id]();
  expect(mockPlayTrack).toHaveBeenCalledWith(mockTrackB);

  // Step 2: Simulate track B now playing
  mockPlayTrack.mockClear();
  mockUseComparisonStore.mockReturnValue({
    currentPair: {
      session_id: 1,
      track_a: mockTrackA,
      track_b: mockTrackB,
    },
    playingTrack: mockTrackB,
    comparisonsCompleted: 5,
    isComparisonMode: true,
    sessionId: '1',
    prefetchedPair: null,
    priorityPathPrefix: null,
    setSession: vi.fn(),
    setPlaying: vi.fn(),
    incrementCompleted: vi.fn(),
    reset: vi.fn(),
    setCurrentPair: vi.fn(),
    advanceToNextPair: vi.fn(),
    setPriorityPath: vi.fn(),
  });
  rerender();

  // Step 3: Track B finishes → should switch back to track A
  expect(capturedCallbacks[mockTrackB.id]).toBeDefined();
  capturedCallbacks[mockTrackB.id]();
  expect(mockPlayTrack).toHaveBeenCalledWith(mockTrackA);

  // Verify the loop can continue indefinitely
  expect(mockPlayTrack).toHaveBeenCalledTimes(1); // Only the switch from B to A
});
```

## Acceptance Criteria

- ✅ New test added to ComparisonView.test.tsx
- ✅ Test passes with `npx vitest run src/components/ComparisonView.test.tsx`
- ✅ Test verifies complete A→B→A looping cycle
- ✅ Test increases coverage of looping behavior
- ✅ Clean commit with conventional commit message

## Test Commands

```bash
cd web/frontend
npx vitest run src/components/ComparisonView.test.tsx
```

## Commit Message

```
test: add end-to-end test for complete looping cycle
```

## Dependencies

- Task 01 must be complete (tests must be passing)

## Notes

- This is an integration test that verifies the complete looping behavior
- Uses mock callbacks to simulate track finish events
- Tests both directions of the loop (A→B and B→A)
- Focuses on behavioral verification, not implementation details
