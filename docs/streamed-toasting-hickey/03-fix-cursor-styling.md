---
task: 03-fix-cursor-styling
status: done
depends: [02-implement-drag-preview-row]
files:
  - path: web/frontend/src/pages/PlaylistOrganizer.tsx
    action: modify
---

# Fix Cursor Styling Throughout Drag Operation

## Context
The cursor changes from `grab` to other cursors during drag operations, creating inconsistent UX. This task ensures the `cursor-grabbing` (closed fist) cursor is applied throughout the entire drag operation using a global cursor override pattern.

## Files to Modify
- `web/frontend/src/pages/PlaylistOrganizer.tsx` (modify)

## Implementation Details

### Step 1: Verify DragPreviewRow cursor styling

The `DragPreviewRow` component created in task 02 includes `cursor-grabbing` in its root div:

```tsx
<div className="bg-obsidian-surface border-2 border-obsidian-accent rounded shadow-2xl cursor-grabbing transform scale-105 opacity-95">
```

This provides cursor styling when hovering over the preview element itself.

### Step 2: Verify existing drag handle cursor styling

The drag handles in `UnassignedTrackTable.tsx` and `Bucket.tsx` already have:
```tsx
className="cursor-grab active:cursor-grabbing"
```

This gives the correct cursor states:
- **At rest**: `cursor-grab` (open hand)
- **On click/drag**: `cursor-grabbing` (closed fist)

### Step 3: Implement global cursor override

Add global cursor override to ensure consistent `cursor-grabbing` throughout the entire drag operation, regardless of what element the cursor hovers over.

In `handleDragStart`, add cursor override after setting state:

```tsx
const handleDragStart = useCallback((event: DragStartEvent) => {
  const { active } = event;
  setActiveId(active.id as number);
  setActiveDragType(active.data.current?.type as 'unassigned-track' | 'bucket-track');

  // Global cursor override for consistent drag UX
  document.body.style.cursor = 'grabbing';
}, []);
```

In `handleDragEnd`, reset cursor at the start of the function (before the drag lock check):

```tsx
const handleDragEnd = useCallback(async (event: DragEndEvent): Promise<void> => {
  // Reset cursor immediately
  document.body.style.cursor = '';

  // Prevent concurrent drag operations
  if (isDragOperationInProgress.current) {
    console.warn('Drag operation already in progress, ignoring');
    return;
  }

  // ... rest of existing logic ...
}, [/* deps */]);
```

**Why global override is recommended**:
- Standard pattern in drag-and-drop implementations
- Ensures cursor consistency even if cursor moves faster than DragOverlay rendering
- Current DragOverlay already uses `cursor-grabbing` (line 483) but issues persist
- Minimal trade-off: only affects document during 1-2 second drag operation

## Verification

1. Start dev server: `music-minion --web`
2. Navigate to playlist organizer
3. **Hover test**:
   - Hover over drag handle (grip icon)
   - **Expected**: Cursor shows `grab` (open hand)
4. **Drag start test**:
   - Click and start dragging
   - **Expected**: Cursor changes to `grabbing` (closed fist) immediately
   - **Expected**: Global cursor override takes effect
5. **Drag movement test**:
   - Move cursor around while dragging (over table, over buckets, over empty space)
   - **Expected**: Cursor remains `grabbing` throughout entire drag
   - **Expected**: Cursor does NOT change to default or pointer regardless of element hovering
6. **Drag end test**:
   - Drop the track
   - **Expected**: Cursor immediately returns to normal (default or grab if still hovering handle)
7. **Cancel test**:
   - Start dragging, then press Escape
   - **Expected**: Cursor resets properly
8. Test on both unassigned and bucket drags
9. Test in Chrome and Firefox if possible (cursor rendering can differ)
