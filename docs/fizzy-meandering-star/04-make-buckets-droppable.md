---
task: 04-make-buckets-droppable
status: done
depends: [03-make-unassigned-tracks-draggable]
files:
  - path: web/frontend/src/components/organizer/Bucket.tsx
    action: modify
---

# Make Buckets Droppable

## Context
Make bucket headers into drop zones that accept dragged tracks from the unassigned table. Add visual feedback (highlighting) when dragging over a bucket, and auto-expand collapsed buckets after hovering for 500ms. Preserve existing within-bucket track reordering functionality.

## Files to Modify
- `web/frontend/src/components/organizer/Bucket.tsx` (modify)

## Implementation Details

### 1. Add Imports
Add at the top:
```typescript
import { useDroppable } from '@dnd-kit/core';
import { useEffect } from 'react'; // If not already imported
```

### 2. Add Droppable Hook
Add after line 89 (inside the BucketComponent function):

```typescript
const { setNodeRef: setDropRef, isOver } = useDroppable({
  id: bucket.id,
  data: { type: 'bucket' }, // Required for drop target validation in PlaylistOrganizer
});

// Auto-expand on drag hover
useEffect(() => {
  if (isOver && !isExpanded) {
    const timer = setTimeout(() => setIsExpanded(true), 500);
    return () => clearTimeout(timer);
  }
}, [isOver, isExpanded, setIsExpanded]);
```

### 3. Update Bucket Header
Update the header div (line 129) to use the drop ref and highlight on hover:

```typescript
<div
  ref={setDropRef}
  className={`flex items-center gap-2 px-3 py-2 transition-colors ${
    isOver ? 'bg-obsidian-accent/20 border-obsidian-accent' : ''
  }`}
>
```

### 4. Update handleDragEnd
Modify the `handleDragEnd` function (lines 111-120) to only handle within-bucket reordering (cross-bucket assignment is handled by PlaylistOrganizer):

```typescript
const handleDragEnd = (event: DragEndEvent): void => {
  const { active, over } = event;

  // Only handle if dragging within this bucket's SortableContext
  // Skip if dragging unassigned-track (handled by parent DndContext)
  if (over && active.id !== over.id && active.data.current?.type !== 'unassigned-track') {
    const oldIndex = trackIds.indexOf(active.id as number);
    const newIndex = trackIds.indexOf(over.id as number);
    const newOrder = arrayMove(trackIds, oldIndex, newIndex);
    onReorderTracks(newOrder);
  }
};
```

### 5. Keep Local DndContext for Within-Bucket Reordering
Keep the existing DndContext wrapper inside the expanded tracks section (lines 232-245). This enables within-bucket track reordering while the parent DndContext handles cross-bucket operations.

**Important**: Do NOT remove the DndContext from the bucket's track list. The architecture uses nested contexts:
- Parent DndContext (PlaylistOrganizer) - handles unassigned → bucket
- Child DndContext (Bucket) - handles track reordering within bucket

### 6. Update Empty Bucket Message
Update the empty bucket message (around line 316) to mention drag-and-drop:

```typescript
<div className="px-3 py-4 text-center text-sm text-white/40">
  No tracks assigned. Drag a track here or press Shift+{shortcutNumber}.
</div>
```

### Architecture Notes
- **Nested DndContext**: Parent context handles cross-component drags, child context handles within-bucket reordering
- **Type-based validation**: Bucket headers tagged with `data: { type: 'bucket' }` for drop target validation in PlaylistOrganizer
- **Type filtering**: `handleDragEnd` checks `type !== 'unassigned-track'` to avoid interfering with parent's handling
- **Auto-expand delay**: 500ms prevents accidental expansion during quick mouse movements (useEffect dependency array includes setIsExpanded for exhaustive-deps compliance)
- **Visual hierarchy**: Drop zone highlight uses accent color at 20% opacity

## Verification

### Basic Drag-and-Drop
1. Navigate to playlist organizer with unassigned tracks and at least one bucket
2. Grab an unassigned track by the drag handle
3. Drag over a bucket header → Header should highlight with accent color
4. Drop on the bucket → Track disappears from unassigned table and appears in the bucket
5. Next unassigned track should auto-play

### Auto-Expand Feature
1. Ensure a bucket is collapsed (not showing tracks)
2. Drag an unassigned track over the collapsed bucket header
3. Hold mouse over header for ~500ms
4. Bucket should auto-expand to show track list
5. Release drag → Track assigns to bucket

### Regression Testing
1. **Within-bucket reordering**: Expand a bucket with multiple tracks, drag tracks to reorder them → Should still work
2. **Bucket controls**: Test up/down arrows, shuffle, edit, delete buttons → Should all still work
3. **Click interactions**: Clicking bucket header (not during drag) should expand/collapse → Should work
4. **Keyboard shortcuts**: Shift+1 through Shift+9 → Should still assign tracks

### Edge Cases
1. **No buckets exist**: Drag unassigned track → No valid drop zones, track returns to original position
2. **Drag currently playing track**: Should work, track assigns and next track auto-plays
3. **Rapid operations**: Drag track, immediately press Shift+2 → Both operations should complete
4. **Empty bucket**: Drag track to empty bucket → Track appears, bucket shows 1 track
5. **Full bucket**: Drag track to bucket with many tracks → Track appends to end

### Performance
1. Test with 100+ unassigned tracks → Virtual scrolling should remain smooth
2. Test with 10+ buckets → Drag-and-drop should have no lag
3. Test on mobile device → Touch drag should work without scrolling issues
