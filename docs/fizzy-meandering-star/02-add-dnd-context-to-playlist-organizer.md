---
task: 02-add-dnd-context-to-playlist-organizer
status: done
depends: [01-fix-keyboard-shortcuts]
files:
  - path: web/frontend/src/pages/PlaylistOrganizer.tsx
    action: modify
---

# Add DndContext to PlaylistOrganizer

## Context
Enable cross-component drag-and-drop by lifting DndContext from individual bucket components to the PlaylistOrganizer level. This allows tracks to be dragged from the unassigned table to any bucket. The @dnd-kit library is already installed and used for within-bucket reordering.

## Files to Modify
- `web/frontend/src/pages/PlaylistOrganizer.tsx` (modify)

## Implementation Details

### 1. Add Imports
Add at the top of the file:
```typescript
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core';
import { toast } from 'react-toastify';
```

**Note**: This requires react-toastify to be installed and configured (see README.md for setup steps).

### 2. Add Sensors Configuration
Add inside the PlaylistOrganizer component (same pattern as Bucket.tsx):
```typescript
const sensors = useSensors(
  useSensor(PointerSensor, {
    activationConstraint: { distance: 8 }, // Prevents accidental drags
  }),
  useSensor(KeyboardSensor)
);
```

### 3. Add Auto-Advance Helper Function
Extract the auto-advance logic into a reusable function (used by both keyboard shortcuts and drag-and-drop):
```typescript
const playNextUnassignedTrack = useCallback((excludeTrackId: number) => {
  const remainingUnassigned = unassignedTrackIds.filter(id => id !== excludeTrackId);
  if (remainingUnassigned.length > 0 && allTracks?.tracks) {
    const nextTrack = allTracks.tracks.find(t => t.id === remainingUnassigned[0]);
    if (nextTrack) {
      play(
        { id: nextTrack.id, title: nextTrack.title, artist: nextTrack.artist },
        { type: 'playlist', playlist_id: playlistId }
      );
    }
  }
}, [unassignedTrackIds, allTracks, playlistId, play]);
```

### 4. Add Drag End Handler
Add this handler to route drag events with validation and error handling:
```typescript
const handleDragEnd = async (event: DragEndEvent): Promise<void> => {
  const { active, over } = event;

  if (!over) return;

  const dragType = active.data.current?.type;

  if (dragType === 'unassigned-track') {
    // Validate drop target is a bucket
    if (over.data.current?.type !== 'bucket') return;

    const trackId = active.id as number;
    const bucketId = over.id as string;

    try {
      await assignTrack(bucketId, trackId);
      playNextUnassignedTrack(trackId);
    } catch (error) {
      console.error('Failed to assign track:', error);
      toast.error('Failed to assign track to bucket');
    }
  }
  // bucket-track type is handled by SortableContext within buckets
};
```

### 5. Update Keyboard Shortcut Handler
Update the existing keyboard shortcut handler to use the extracted `playNextUnassignedTrack` function instead of duplicating the logic. Replace the auto-advance code in the keyboard handler (around lines 95-97) with:
```typescript
handleAssignCurrentTrack(bucket.id);
playNextUnassignedTrack(currentTrack.id);
```

### 6. Wrap JSX Return
Wrap the entire return statement content with DndContext (around line 150+):
```typescript
return (
  <DndContext
    sensors={sensors}
    collisionDetection={closestCenter}
    onDragEnd={handleDragEnd}
  >
    <div className="min-h-screen bg-black font-inter p-6">
      {/* All existing content stays here */}
    </div>
  </DndContext>
);
```

### Architecture Notes
- **Type-based routing**: The `dragType` field distinguishes between:
  - `"unassigned-track"` - dragging from unassigned table to bucket
  - `"bucket-track"` - dragging within buckets (handled by SortableContext in Bucket.tsx)
- **Drop target validation**: Checks `over.data.current?.type === 'bucket'` to ensure tracks only drop on valid buckets
- **Auto-advance behavior**: Extracted into `playNextUnassignedTrack` function, shared by keyboard shortcuts and drag-and-drop
- **Error handling**: Try/catch with toast notification for failed assignments, React Query auto-reverts optimistic updates
- **Collision detection**: Uses `closestCenter` to determine drop target

## Verification

1. After implementation, verify the component still renders correctly
2. No TypeScript errors in the file
3. The page loads without JavaScript console errors
4. Existing functionality (keyboard shortcuts, click-to-play) still works

**Note**: Actual drag-and-drop won't work yet - that requires the next two tasks (making unassigned tracks draggable and buckets droppable).
