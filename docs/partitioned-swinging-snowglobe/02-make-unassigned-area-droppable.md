---
task: 02-make-unassigned-area-droppable
status: done
depends: [01-update-bucket-drag-handlers]
files:
  - path: web/frontend/src/components/organizer/UnassignedTrackTable.tsx
    action: modify
---

# Make Unassigned Area Droppable

## Context

Add a droppable zone to the unassigned track table so bucket tracks can be dragged back to unassigned status. The entire table container becomes a drop target with visual feedback on hover.

## Files to Modify

- `web/frontend/src/components/organizer/UnassignedTrackTable.tsx` (modify)

## Implementation Details

### Change 1: Import useDroppable

**Location**: Line 11

Add `useDroppable` to the imports from `@dnd-kit/core`:

```typescript
import { useDraggable, useDroppable } from '@dnd-kit/core';
```

### Change 2: Add Droppable Hook

**Location**: After line 26 (inside UnassignedTrackTable component, after parentRef)

Add the droppable hook:

```typescript
// Make container droppable for bucket tracks
const { setNodeRef: setDroppableRef, isOver } = useDroppable({
  id: 'unassigned-area',
  data: { type: 'unassigned-area' },
});
```

**Droppable Type**: Using `'unassigned-area'` to distinguish from `'bucket'` type and track types.

### Change 3: Apply Ref and Hover Styling

**Location**: Line 196 (main container div in return statement)

Update the **outermost container div** to use the droppable ref and show visual feedback:

```typescript
<div
  ref={setDroppableRef}
  data-testid="unassigned-droppable"
  className={`border border-obsidian-border rounded-lg overflow-hidden ${
    isOver ? 'ring-2 ring-obsidian-accent' : ''
  }`}
>
```

**Important**: Apply `setDroppableRef` to the outer container div (line 196), NOT the inner scrollable div (line 199-200) which already uses `parentRef` for virtual scrolling. The outer container wraps both desktop and mobile views.

**Visual Feedback**: When a bucket track is dragged over the unassigned area, it shows a 2px accent-colored ring around the container.

**Why entire container?** Larger drop target is easier to hit than just the header. More intuitive UX - users expect to drop anywhere in the unassigned area.

## Verification

1. Build TypeScript: `npx tsc --noEmit`
   - Should compile with no errors

2. Start web mode: `music-minion --web`
   - Navigate to playlist organizer with at least one bucket containing tracks

3. Test droppable zone visual feedback:
   - Expand a bucket with tracks
   - Grab a track by its drag handle
   - Drag it over the unassigned table area
   - **Expected**: Unassigned table should show a 2px accent-colored ring when hovering with the dragged track
   - **Note**: The drop won't actually work yet - that requires the parent handler update in Task 03

4. Test existing functionality still works:
   - Drag unassigned tracks to buckets → should still work
   - Click unassigned tracks to play → should still work
   - Virtual scrolling in unassigned table → should still work smoothly
