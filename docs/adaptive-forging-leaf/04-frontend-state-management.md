---
task: 04-frontend-state-management
status: pending
depends: [03-backend-player-integration]
files:
  - path: web/frontend/src/stores/playerStore.ts
    action: modify
---

# Frontend State Management - Player Store Updates

## Context
Update the Zustand player store to handle sort state, add smooth shuffle toggle action, and add manual sort action. Sync state via WebSocket broadcasts from backend.

## Files to Modify/Create
- web/frontend/src/stores/playerStore.ts (modify)

## Implementation Details

### Add State Fields

Update the `PlayerState` interface:

```typescript
interface PlayerState {
  // ... existing fields ...
  currentTrack: Track | null;
  queue: Track[];
  queueIndex: number;
  isPlaying: boolean;
  shuffleEnabled: boolean;

  // NEW: Sort state
  sortField: string | null;
  sortDirection: 'asc' | 'desc' | null;
}
```

### Add Actions

Update the `PlayerActions` interface and implementation:

```typescript
interface PlayerActions {
  // ... existing actions ...
  play: (track: Track, context?: PlayContext) => Promise<void>;
  pause: () => Promise<void>;
  next: () => Promise<void>;
  toggleShuffle: () => void;  // KEEP for backward compat

  // NEW: Smooth shuffle toggle (doesn't reset position)
  toggleShuffleSmooth: () => Promise<void>;

  // NEW: Set manual sort order
  setSortOrder: (field: string, direction: 'asc' | 'desc') => Promise<void>;
}
```

### Implement toggleShuffleSmooth()

Replace the current shuffle toggle logic with smooth toggle:

```typescript
toggleShuffleSmooth: async () => {
  const { shuffleEnabled, currentTrack } = get();

  try {
    const response = await fetch(`${API_BASE}/player/toggle-shuffle`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error('Failed to toggle shuffle');
    }

    const data = await response.json();

    // Optimistic update (will be confirmed via WebSocket)
    set({
      shuffleEnabled: data.shuffle_enabled,
      sortField: null,
      sortDirection: null,
    });

    logger.info(`Shuffle ${data.shuffle_enabled ? 'enabled' : 'disabled'} (smooth toggle)`);
  } catch (error) {
    logger.exception('Error toggling shuffle');
    set({ playbackError: (error as Error).message });
  }
},
```

### Implement setSortOrder()

Add new action for manual table sorting:

```typescript
setSortOrder: async (field: string, direction: 'asc' | 'desc') => {
  try {
    const response = await fetch(`${API_BASE}/player/set-sort`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ field, direction }),
    });

    if (!response.ok) {
      throw new Error('Failed to set sort order');
    }

    const data = await response.json();

    // Optimistic update
    set({
      sortField: field,
      sortDirection: direction,
      shuffleEnabled: false,  // Sort disables shuffle
    });

    logger.info(`Queue sorted by ${field} ${direction}`);
  } catch (error) {
    logger.exception('Error setting sort order');
    set({ playbackError: (error as Error).message });
  }
},
```

### Update syncState() for WebSocket

Modify the `syncState()` action to handle sort state from backend broadcasts:

```typescript
syncState: (state: PlaybackState & { serverTime: number }) => {
  const currentState = get();

  // Extract sort spec from backend state
  const sortField = state.sortSpec?.field ?? null;
  const sortDirection = state.sortSpec?.direction ?? null;

  // Sync all state
  set({
    currentTrack: state.currentTrack,
    queue: state.queue,
    queueIndex: state.queueIndex,
    isPlaying: state.isPlaying,
    positionMs: state.positionMs,
    trackStartedAt: state.trackStartedAt,
    shuffleEnabled: state.shuffleEnabled,

    // NEW: Sync sort state
    sortField,
    sortDirection,

    // ... other fields ...
  });

  // Calculate derived playback position based on server time
  if (state.isPlaying && state.trackStartedAt) {
    const serverNow = state.serverTime;
    const elapsed = (serverNow - state.trackStartedAt) * 1000;
    const syncedPosition = state.positionMs + elapsed;
    set({ positionMs: syncedPosition });
  }
},
```

### Update Initial State

Set default values for new fields:

```typescript
const usePlayerStore = create<PlayerState & PlayerActions>((set, get) => ({
  // ... existing initial state ...
  shuffleEnabled: JSON.parse(localStorage.getItem('music-minion-shuffle') ?? 'true'),

  // NEW: Sort state defaults
  sortField: null,
  sortDirection: null,

  // ... actions ...
}));
```

### Keep Legacy toggleShuffle() for Backward Compatibility

The old `toggleShuffle()` can remain for now (calls the old re-fetch logic), but update the PlayerBar to use `toggleShuffleSmooth()`.

```typescript
toggleShuffle: () => {
  const { shuffleEnabled, currentContext, currentTrack } = get();
  const newShuffleEnabled = !shuffleEnabled;

  localStorage.setItem('music-minion-shuffle', JSON.stringify(newShuffleEnabled));
  set({ shuffleEnabled: newShuffleEnabled });

  // Legacy behavior: Re-fetch queue (resets position)
  if (currentContext && currentTrack) {
    fetch(`${API_BASE}/player/play`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        trackId: currentTrack.id,
        context: { ...currentContext, shuffle: newShuffleEnabled },
      }),
    });
  }
},
```

## Verification

```bash
# Start dev server
cd web/frontend
npm run dev

# Open browser console at http://localhost:5173
# Check player store

# 1. Play a playlist and check state
const { shuffleEnabled, sortField, queue } = usePlayerStore.getState()
console.log('Shuffle:', shuffleEnabled, 'Sort:', sortField, 'Queue size:', queue.length)

# 2. Toggle shuffle smoothly
usePlayerStore.getState().toggleShuffleSmooth()
# Check that current track unchanged, queue rebuilt

# 3. Set manual sort
usePlayerStore.getState().setSortOrder('bpm', 'asc')
# Check shuffleEnabled = false, sortField = 'bpm'

# 4. WebSocket sync test
# Open app in two browser tabs
# Toggle shuffle in tab 1
# Verify tab 2 syncs automatically
```

**Expected behavior:**
- `sortField` and `sortDirection` persist in state
- `toggleShuffleSmooth()` doesn't interrupt playback
- `setSortOrder()` disables shuffle automatically
- WebSocket broadcasts update all connected clients
- localStorage still saves shuffle preference
