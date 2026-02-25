---
task: 01-add-drag-overlay-to-playlist-organizer
status: done
depends: []
files:
  - path: web/frontend/src/pages/PlaylistOrganizer.tsx
    action: modify
---

# Add DragOverlay to PlaylistOrganizer

## Context

The playlist organizer is missing visual feedback during drag operations - dragged tracks become invisible once they leave their source container. This happens because there's no `DragOverlay` component to show a preview of what's being dragged. This task adds the DragOverlay component along with the necessary drag state tracking to make dragged items visible throughout the entire drag operation.

## Files to Modify

- `web/frontend/src/pages/PlaylistOrganizer.tsx` (modify)

## Implementation Details

### Step 1: Import DragOverlay, DragStartEvent, and useState

Update React imports to include useState:
```tsx
import { useEffect, useCallback, useState, useMemo } from 'react';
```

Add to imports from `@dnd-kit/core`:
```tsx
import {
  DndContext,
  DragOverlay,  // ADD THIS
  closestCenter,
  pointerWithin,
  // ... rest
} from '@dnd-kit/core';
```

Update type imports:
```tsx
import type { DragEndEvent, DragStartEvent } from '@dnd-kit/core';
```

### Step 2: Add Active Drag State

After the sensors definition, add state to track active drag:
```tsx
const [activeId, setActiveId] = useState<number | null>(null);
const [activeDragType, setActiveDragType] = useState<'unassigned-track' | 'bucket-track' | null>(null);
```

### Step 3: Add onDragStart Handler

Before the `handleDragEnd` function, add:
```tsx
const handleDragStart = useCallback((event: DragStartEvent) => {
  const { active } = event;
  setActiveId(active.id as number);
  setActiveDragType(active.data.current?.type as 'unassigned-track' | 'bucket-track');
}, []);
```

### Step 4: Add onDragCancel Handler

After `handleDragStart`:
```tsx
const handleDragCancel = useCallback(() => {
  setActiveId(null);
  setActiveDragType(null);
}, []);
```

### Step 5: Update handleDragEnd to Clear State

Wrap the existing `handleDragEnd` logic in try-finally to ensure state cleanup even on early returns:
```tsx
const handleDragEnd = useCallback(
  async (event: DragEndEvent): Promise<void> => {
    try {
      const { active, over } = event;
      if (!over) return;

      // ... all existing drag handling logic ...

    } finally {
      // Always clear state, even if early return or error
      setActiveId(null);
      setActiveDragType(null);
    }
  },
  [assignTrack, unassignTrack, playNextUnassignedTrack]
);
```

**Note**: The try-finally ensures cleanup happens even if the function returns early (e.g., `if (!over) return;`)

### Step 6: Add Memoized Track Display Logic

After the `handleDragCancel` function, add useMemo to compute the active track display efficiently:

```tsx
// Memoize track display to avoid O(n*m) lookup on every render
const activeTrackDisplay = useMemo(() => {
  if (!activeId || !activeDragType) return null;

  if (activeDragType === 'unassigned-track') {
    const track = unassignedTracks.find(t => t.id === activeId);
    return track ? track.title : 'Unknown Track';
  }

  // Bucket track - find in buckets
  for (const bucket of buckets) {
    const track = bucket.tracks.find(t => t.id === activeId);
    if (track) return `${bucket.emoji_id || '📦'} ${track.title}`;
  }
  return 'Unknown Track';
}, [activeId, activeDragType, unassignedTracks, buckets]);
```

**Why**: This prevents re-computing the track lookup on every render frame during drag, improving performance.

### Step 7: Add DragOverlay Component

Inside `<DndContext>`, after all content but before closing `</DndContext>` tag, add:

```tsx
<DragOverlay>
  {activeTrackDisplay ? (
    <div className="bg-obsidian-surface border border-obsidian-accent rounded px-3 py-2 shadow-xl opacity-90 cursor-grabbing">
      <div className="text-sm text-white/90 truncate max-w-md">
        {activeTrackDisplay}
      </div>
    </div>
  ) : null}
</DragOverlay>
```

**Note**: We removed `dropAnimation={null}` to use the default snap-back animation for better UX.

### Step 8: Pass New Handlers to DndContext

Update `<DndContext>` props:
```tsx
<DndContext
  sensors={sensors}
  collisionDetection={pointerWithin}
  onDragStart={handleDragStart}  // ADD
  onDragEnd={handleDragEnd}
  onDragCancel={handleDragCancel}  // ADD
>
```

## Why This Works

1. **Visual Feedback**: DragOverlay shows a preview of the dragged item that follows the cursor
2. **Cross-Context Visibility**: Rendered at the top-level DndContext, visible across nested bucket contexts
3. **Z-Index Stacking**: Appears above all other elements via portal rendering
4. **State Management**: onDragStart captures what's being dragged, onDragEnd/onDragCancel clear state

## Verification

1. **TypeScript compilation**: `npx tsc --noEmit` (from web/frontend)
   - Should pass with no errors

2. **Start web mode**: `music-minion --web`
   - Navigate to playlist organizer
   - Open browser console (F12) to check for errors

3. **Test unassigned track dragging**:
   - Grab an unassigned track by its drag handle
   - **Expected**: See a preview box following your cursor showing the track title
   - **Expected**: No errors in console (verify drag data is complete)
   - Hover over a bucket header → should highlight
   - Drop on bucket → should assign
   - **Expected**: Preview animates to final position and disappears
   - **Critical**: Verify no "Unknown Track" appears unless track is actually missing

4. **Test bucket track dragging**:
   - Grab a track from a bucket
   - **Expected**: See preview following cursor with bucket emoji + track title
   - Move cursor outside the bucket
   - **Expected**: Preview remains visible (not disappearing)
   - Hover over another bucket header → should highlight
   - **Expected**: Can see both the preview AND the highlight
   - Drop on different bucket → should move
   - **Expected**: Track appears in new bucket, removed from old

5. **Test bucket → unassigned**:
   - Grab a bucket track
   - Hover over unassigned area → should show ring highlight
   - Drop → should move to unassigned
   - **Expected**: Bucket emoji removed from track

6. **Test within-bucket reordering** (verify no regression):
   - Drag track within same bucket
   - **Expected**: Track reorders smoothly
   - **Expected**: Preview still visible during drag

7. **Edge cases**:
   - Drag and press Escape → should cancel, preview disappears
   - Drag to invalid area and release → track returns to origin, preview disappears
   - Rapid drags → no lag, smooth experience
