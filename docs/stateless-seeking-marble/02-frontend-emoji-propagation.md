---
task: 02-frontend-emoji-propagation
status: running
depends: [01-backend-emoji-sync]
files:
  - path: web/frontend/src/hooks/useSyncWebSocket.ts
    action: modify
---

# Frontend: Handle Emoji Updates via WebSocket

## Context
After backend broadcasts a `track:emojis_updated` event via WebSocket, the frontend needs to update playerStore so the UI reflects the new emojis immediately. This follows the existing pattern used for `playback:state` updates.

## Files to Modify/Create
- web/frontend/src/hooks/useSyncWebSocket.ts (modify)

## Implementation Details

Add a new case in `handleMessage` switch statement to handle `track:emojis_updated` events:

**Add new case in handleMessage switch:**
```typescript
case 'track:emojis_updated': {
  const { track_id, emojis } = data;
  const { currentTrack, queue, set } = usePlayerStore.getState();

  // Update currentTrack if it matches
  const updatedCurrentTrack = currentTrack?.id === track_id
    ? { ...currentTrack, emojis }
    : currentTrack;

  // Update queue if track is in it
  const updatedQueue = queue.map(t =>
    t.id === track_id ? { ...t, emojis } : t
  );

  // Only update if something changed
  if (updatedCurrentTrack !== currentTrack || updatedQueue !== queue) {
    set({ currentTrack: updatedCurrentTrack, queue: updatedQueue });
  }

  // Also update comparisonStore if track is in current pair
  const { currentPair, updateTrackInPair } = useComparisonStore.getState();
  if (currentPair?.track_a.id === track_id) {
    updateTrackInPair({ ...currentPair.track_a, emojis });
  } else if (currentPair?.track_b.id === track_id) {
    updateTrackInPair({ ...currentPair.track_b, emojis });
  }
  break;
}
```

**Note**: The existing imports for `usePlayerStore` and `useComparisonStore` are already present in the file.

## Why WebSocket Instead of Direct Store Mutation

1. **Matches existing pattern**: `playback:state` already updates playerStore via WebSocket
2. **Multi-device sync**: All connected devices see emoji updates immediately
3. **Decoupled**: quickTagStore stays pure (just votes), doesn't import other stores
4. **Future-proof**: Any new store/component showing track emojis can subscribe to the same event

## Verification

1. Start full app: `music-minion --web`
2. Play a track from any playlist
3. Navigate to Comparison page with the playing track in the pair
4. Use Quick Tag in sidebar to vote on a dimension (e.g., click ⚡ for energy)
5. **Verify immediately**: The track card should show the ⚡ emoji without page refresh
6. Navigate to Home page - Now Playing section should also show the emoji
7. Test changing vote: Vote the opposite emoji and verify it swaps
8. Test skip: Vote "0" (dash button) and verify the dimension emojis are removed
9. **Multi-device test**: Open app in second browser tab, vote in one, verify emoji appears in both
