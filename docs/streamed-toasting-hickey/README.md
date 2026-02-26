# Fix Drag-and-Drop Visual Feedback and Scroll Issues

## Overview

This plan fixes UX issues in the Music Minion playlist organizer's drag-and-drop system. After removing the `useDroppable` container (which resolved "Maximum update depth" errors), drag-and-drop works functionally but has poor visual feedback:

- Rows disappear when dragging with no visible preview
- Cursor changes inconsistently during drag operations
- Unassigned tracks list auto-scrolls to bottom when dragging unassigned tracks
- No rich visual representation of the dragged item

This plan implements three improvements:
1. Prevent virtual scrolling during drag operations (unassigned tracks only)
2. Create a full-row drag preview component showing all track data
3. Ensure consistent cursor styling throughout drag lifecycle using global cursor override

**Scope**: Desktop drag-and-drop only. Mobile drag-and-drop is out of scope for this plan.

**Prerequisites**: Commit uncommitted changes in `PlaylistOrganizer.tsx` and `UnassignedTrackTable.tsx` before starting implementation.

## Task Sequence

1. [01-prevent-scroll-during-drag.md](./01-prevent-scroll-during-drag.md) - Disable virtual scroll container overflow during active drags
2. [02-implement-drag-preview-row.md](./02-implement-drag-preview-row.md) - Create DragPreviewRow component with full column layout
3. [03-fix-cursor-styling.md](./03-fix-cursor-styling.md) - Verify cursor-grabbing styling throughout drag operation

## Success Criteria

After implementing all tasks, verify end-to-end:

### Visual Feedback Test
1. Navigate to `/playlist-organizer/{playlistId}`
2. Drag an unassigned track
3. **✓** Full-row preview appears under cursor with all columns (drag handle, title, artist, BPM, key, rating)
4. **✓** Preview has elevated styling (shadow, accent border, slight scale)
5. **✓** Preview follows cursor smoothly

### Scroll Prevention Test
1. Scroll unassigned tracks list to middle position
2. Start dragging a track
3. **✓** List does NOT auto-scroll to bottom
4. **✓** Scroll position remains locked during drag
5. Drop track and verify scrolling re-enables

### Cursor Test
1. Hover over drag handle: **✓** `grab` (open hand)
2. Start dragging: **✓** `grabbing` (closed fist)
3. Move cursor during drag: **✓** `grabbing` remains throughout
4. Drop track: **✓** Cursor returns to normal

### Functional Test
1. **✓** Drag unassigned track to bucket → assigns correctly
2. **✓** Drag bucket track to different bucket → moves correctly
3. **✓** Drag bucket track outside zones → unassigns (returns to unassigned)
4. **✓** All operations work without errors or infinite loops

### Cross-Browser Test (if possible)
1. **✓** Test in Chrome and Firefox
2. **✓** DragOverlay renders identically
3. **✓** Cursor behavior is consistent

## Dependencies

- **React**: Already installed
- **@dnd-kit/core**: Already installed
- **TanStack Virtual**: Already installed
- **Lucide React** (for GripVertical icon): Already installed

## Implementation Notes

- Keep `opacity: isDragging ? 0 : 1` pattern in `DraggableRow` - this is correct for DragOverlay usage
- Virtual scrolling remains enabled for performance, only scroll is disabled during unassigned track drags
- DragPreviewRow flex values match UnassignedTrackTable exactly: title (flex-[3]), artist (flex-[2]), fixed widths for BPM/key/rating
- Works for both unassigned and bucket tracks (same PlaylistTrackEntry type)
- `trackIdToTrackMap` changed from storing `{title, artist}` to full `PlaylistTrackEntry` objects for DragPreviewRow to access all fields
- Global cursor override (task 03) implemented proactively as standard drag-and-drop pattern
- Default drop animation preserved for smooth visual feedback (no `dropAnimation={null}`)
