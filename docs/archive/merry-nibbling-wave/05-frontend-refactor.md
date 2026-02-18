---
task: 05-frontend-refactor
status: done
depends: [04-backend-api-refactor]
files:
  - path: web/frontend/src/stores/comparisonStore.ts
    action: modify
  - path: web/frontend/src/api/comparisons.ts
    action: modify
  - path: web/frontend/src/routes/comparison.tsx
    action: modify
---

# Frontend Refactoring

## Context
Remove session ID, ranking mode, and prefetch from frontend state. Simplify to single playlist-based mode with direct API calls. Update UI to remove mode selector and add completion message.

## Files to Modify/Create
- web/frontend/src/stores/comparisonStore.ts (modify - remove ~60 lines, add ~30 lines)
- web/frontend/src/api/comparisons.ts (modify - remove ~35 lines, add ~15 lines)
- web/frontend/src/routes/comparison.tsx (modify - ~25 lines)

## Implementation Details

### 1. Remove Session, Mode, Prefetch from Store (comparisonStore.ts)

**Remove from interface:**
- `sessionId`
- `rankingMode`
- `prefetchedPair`

**Updated interface:**

```typescript
interface ComparisonState {
  // KEEP: Simplified state
  selectedPlaylistId: number | null;
  currentPair: ComparisonPair | null;
  currentTrack: TrackInfo | null;
  isPlaying: boolean;
  comparisonsCompleted: number;  // Local counter for UI feedback
  priorityPathPrefix: string | null;
  isComparisonMode: boolean;
  autoplay: boolean;
  progress: ComparisonProgress | null;
}

interface ComparisonActions {
  startComparison: (playlistId: number) => Promise<void>;
  recordComparison: (winnerId: number) => Promise<void>;
  reset: () => void;
}
```

**Updated store implementation:**

```typescript
export const useComparisonStore = create<ComparisonState & ComparisonActions>((set, get) => ({
  // State
  selectedPlaylistId: null,
  currentPair: null,
  currentTrack: null,
  isPlaying: false,
  comparisonsCompleted: 0,
  priorityPathPrefix: null,
  isComparisonMode: false,
  autoplay: true,
  progress: null,

  // Actions
  startComparison: async (playlistId: number) => {
    const response = await startComparison(playlistId);
    set({
      selectedPlaylistId: playlistId,
      currentPair: response.pair,
      progress: response.progress,
      isComparisonMode: true,
    });
  },

  recordComparison: async (winnerId: number) => {
    const { selectedPlaylistId, currentPair } = get();
    if (!selectedPlaylistId || !currentPair) return;

    const response = await recordComparison({
      playlist_id: selectedPlaylistId,
      track_a_id: currentPair.track_a.id,
      track_b_id: currentPair.track_b.id,
      winner_id: winnerId,
    });

    set({
      currentPair: response.pair,  // Can be null if ranking complete
      progress: response.progress,
      comparisonsCompleted: get().comparisonsCompleted + 1,
    });

    // Check if ranking complete
    if (!response.pair) {
      // Show completion UI
      set({ isComparisonMode: false });
    }
  },

  reset: () => {
    set({
      selectedPlaylistId: null,
      currentPair: null,
      progress: null,
      isComparisonMode: false,
      comparisonsCompleted: 0,
    });
  },
}));
```

**Delete old actions:**
- `setSession`
- `joinSession`

### 2. Simplify API Client (comparisons.ts)

**Remove session-based functions, keep only:**

```typescript
export async function startComparison(playlistId: number) {
  const response = await api.post('/comparisons/start', { playlist_id: playlistId });
  return response.data;  // {pair, progress}
}

export async function recordComparison(payload: {
  playlist_id: number;
  track_a_id: number;
  track_b_id: number;
  winner_id: number;
}) {
  const response = await api.post('/comparisons/record', payload);
  return response.data;  // {pair, progress}
}
```

**Delete:**
- `startSession`
- `joinSession`
- Any functions that accept `session_id` parameter

### 3. Update Comparison Page UI (comparison.tsx)

**Remove mode selector, add playlist selector:**

```tsx
// Remove mode toggle (global vs playlist)

// Add playlist selector
<PlaylistSelect
  value={selectedPlaylistId}
  onChange={(id) => startComparison(id)}
  placeholder="Select playlist to rank..."
/>

// Show progress
{progress && (
  <div>
    Progress: {progress.compared} / {progress.total} ({progress.percentage}%)
  </div>
)}

// Show completion message when pair is null
{!currentPair && isComparisonMode && (
  <div>
    🎉 Ranking complete! All tracks have been compared.
  </div>
)}
```

**Remove:**
- Mode selector dropdown (`<Select value={rankingMode}>`)
- Conditional playlist selector (show always now)
- Session ID display (if any)

### 4. Prevent "All" Playlist Deletion

Hide or disable delete option for the "All" playlist in any playlist management UI:

```typescript
// In playlist list/management component
const canDelete = (playlist: Playlist) => playlist.name !== "All";

// Hide delete button or show disabled state
{canDelete(playlist) && (
  <DeleteButton onClick={() => handleDelete(playlist.id)} />
)}
```

## Verification

Test in browser:
```bash
# Start web mode
music-minion --web

# Open http://localhost:5173
# Navigate to comparison page
# Verify:
# 1. Only playlist selector visible (no mode toggle)
# 2. Can start comparison for any playlist
# 3. Progress percentage displays correctly
# 4. Completion message shows when all pairs compared
```

Check browser console:
```javascript
const state = useComparisonStore.getState()

// Should NOT have:
// - state.sessionId
// - state.rankingMode
// - state.prefetchedPair

// Should have:
// - state.selectedPlaylistId (number)
// - state.currentPair
// - state.progress
```
