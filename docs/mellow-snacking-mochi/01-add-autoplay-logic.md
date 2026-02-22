---
task: 01-add-autoplay-logic
status: done
depends: []
files:
  - path: web/frontend/src/hooks/useComparison.ts
    action: modify
---

# Add Autoplay Logic to useRecordComparison

## Context
The existing "Autoplay" toggle in the comparison header is currently dead code - the state exists but is never consumed. This task repurposes it to control whether selecting a comparison winner automatically plays track A of the next pair.

- **Autoplay OFF**: Continue playing the current track (existing behavior)
- **Autoplay ON**: Immediately start playing track A of the next comparison pair

## Files to Modify
- `web/frontend/src/hooks/useComparison.ts` (modify)

## Implementation Details

### useComparison.ts

1. Import `usePlayerStore` to access the `play` function
2. Import `useComparisonStore` (already imported, just need store access pattern)
3. In `onSuccess`, read `autoplay` from store directly (avoids stale closure) and trigger playback

```typescript
import { usePlayerStore } from '../stores/playerStore';

export function useRecordComparison() {
  const { recordComparison: updateComparisonState } = useComparisonStore();
  const { play } = usePlayerStore();

  return useMutation({
    mutationFn: (request: RecordComparisonRequest) => recordComparison(request),
    onSuccess: (response) => {
      updateComparisonState(response.pair, response.progress);

      // Auto-play track A of next comparison if enabled
      // Read from store directly to avoid stale closure
      if (useComparisonStore.getState().autoplay && response.pair) {
        const trackIds = [response.pair.track_a.id, response.pair.track_b.id];
        play(response.pair.track_a, { type: 'comparison', track_ids: trackIds, shuffle: false });
      }

      // Prefetch waveforms for the new pair
      if (response.pair) {
        prefetchWaveform(response.pair.track_a.id);
        prefetchWaveform(response.pair.track_b.id);
      }
    },
  });
}
```

## Verification
1. Run TypeScript check: `cd web/frontend && npx tsc --noEmit`
2. Verify no import errors
3. Start app: `music-minion --web`
4. Navigate to comparison page, select a playlist
5. With Autoplay OFF: select winner → next pair loads, current track continues
6. With Autoplay ON: select winner → next pair loads AND track A starts playing
7. Refresh page → toggle state persists (existing localStorage behavior)
