---
task: 05-frontend-ui-updates
status: done
depends: [04-frontend-state-management]
files:
  - path: web/frontend/src/components/player/PlayerBar.tsx
    action: modify
---

# Frontend UI Updates - Smooth Shuffle Button

## Context
Wire the PlayerBar shuffle button to use the new `toggleShuffleSmooth()` action instead of the legacy `toggleShuffle()`. This enables smooth shuffle toggling without playback interruption.

## Files to Modify/Create
- web/frontend/src/components/player/PlayerBar.tsx (modify)
- web/frontend/src/components/queue/QueueTable.tsx (or wherever TanStack Table is used) (modify)

## Implementation Details

### Update Shuffle Button

Find the shuffle button in PlayerBar and update to use `toggleShuffleSmooth()`:

**Before:**
```typescript
const { toggleShuffle, shuffleEnabled } = usePlayer();

<Button
  variant="ghost"
  size="icon"
  onClick={toggleShuffle}
  className={shuffleEnabled ? 'text-obsidian-accent' : 'text-white/60 hover:text-white'}
  title={shuffleEnabled ? 'Shuffle on' : 'Shuffle off'}
>
  <Shuffle className="h-4 w-4" />
</Button>
```

**After:**
```typescript
const { toggleShuffleSmooth, shuffleEnabled } = usePlayer();

<Button
  variant="ghost"
  size="icon"
  onClick={toggleShuffleSmooth}  // CHANGED
  className={shuffleEnabled ? 'text-obsidian-accent' : 'text-white/60 hover:text-white'}
  title={shuffleEnabled ? 'Shuffle on' : 'Shuffle off'}
>
  <Shuffle className="h-4 w-4" />
</Button>
```

### Optional: Add Loading State

For better UX, show loading state during shuffle toggle:

```typescript
const { toggleShuffleSmooth, shuffleEnabled } = usePlayer();
const [isTogglingShuf fle, setIsTogglingShuf fle] = useState(false);

const handleShuffleClick = async () => {
  setIsTogglingShuf fle(true);
  try {
    await toggleShuffleSmooth();
  } finally {
    setIsTogglingShuf fle(false);
  }
};

<Button
  variant="ghost"
  size="icon"
  onClick={handleShuffleClick}
  disabled={isTogglingShuf fle}
  className={shuffleEnabled ? 'text-obsidian-accent' : 'text-white/60 hover:text-white'}
  title={shuffleEnabled ? 'Shuffle on' : 'Shuffle off'}
>
  {isTogglingShuf fle ? (
    <Loader2 className="h-4 w-4 animate-spin" />
  ) : (
    <Shuffle className="h-4 w-4" />
  )}
</Button>
```

### Optional Enhancement: Add Sort State Indicator

If you want to show when manual sort is active:

```typescript
const { shuffleEnabled, sortField, sortDirection } = usePlayer();

<div className="flex items-center gap-1">
  <Button
    variant="ghost"
    size="icon"
    onClick={toggleShuffleSmooth}
    className={shuffleEnabled ? 'text-obsidian-accent' : 'text-white/60 hover:text-white'}
    title={shuffleEnabled ? 'Shuffle on' : 'Shuffle off'}
  >
    <Shuffle className="h-4 w-4" />
  </Button>

  {/* Show sort indicator if manual sort active */}
  {sortField && (
    <span className="text-xs text-white/40">
      {sortField} {sortDirection === 'asc' ? '↑' : '↓'}
    </span>
  )}
</div>
```

### Integrate Column Header Sorting with Backend

Find the queue table component (wherever TanStack Table is configured) and wire column sorting to call the backend API:

**Current (client-side sorting):**
```typescript
const table = useReactTable({
  data: queue,
  columns,
  // ... existing config ...
  onSortingChange: setSorting,
  state: {
    sorting,
  },
});
```

**Updated (backend-driven sorting):**
```typescript
const { setSortOrder } = usePlayerStore();

const table = useReactTable({
  data: queue,
  columns,
  // ... existing config ...
  onSortingChange: (updater) => {
    const newSort = typeof updater === 'function' ? updater(sorting) : updater;

    if (newSort.length > 0) {
      const { id, desc } = newSort[0];
      // Call backend to sort and rebuild queue
      setSortOrder(id, desc ? 'desc' : 'asc');
    }

    // Update local state for UI indicators
    setSorting(newSort);
  },
  state: {
    sorting,
  },
});
```

**Key changes:**
- Extract `setSortOrder` from player store
- When user clicks column header, TanStack calls `onSortingChange`
- Call backend API via `setSortOrder(field, direction)`
- Backend rebuilds queue with new sort order
- WebSocket broadcasts new queue to all clients
- Local `sorting` state updates for visual indicators (↑↓ arrows)

## Verification

```bash
# Start the full stack
uv run music-minion --web

# Open http://localhost:5173

# 1. Play a playlist
# 2. Click shuffle button
# Expected: Current track continues, no audio glitch, queue rebuilds
# 3. Click shuffle button again
# Expected: Smooth toggle back to shuffle mode

# Check browser console for logs:
# "Shuffle enabled (smooth toggle)"
# "Shuffle disabled (smooth toggle)"

# Verify in Network tab:
# POST /api/player/toggle-shuffle
# WebSocket message: playback:state with updated shuffleEnabled
```

**Expected behavior:**
- Clicking shuffle button doesn't interrupt playback
- No position reset to 0:00
- Visual feedback (button color) updates immediately
- Queue table updates with new track order
- Other connected devices sync automatically
