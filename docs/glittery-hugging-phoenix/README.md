# Fix Drag-and-Drop Visibility Issues

## Overview

This plan fixes critical drag-and-drop visibility issues in the Music Minion playlist organizer. Currently, dragged tracks become invisible when users try to move them, making cross-bucket operations impossible and causing crashes when dragging unassigned tracks.

**Root causes:**
1. Missing `DragOverlay` component - no visual representation of dragged items following the cursor
2. No drag state tracking (`onDragStart` handler missing)
3. Nested DndContext isolation prevents proper event propagation

**Solution approach:**
Add the DragOverlay component with proper drag state management to show a visual preview of dragged tracks throughout the entire drag operation. This works across nested contexts and provides consistent visual feedback.

## Task Sequence

1. **[01-add-drag-overlay-to-playlist-organizer.md](./01-add-drag-overlay-to-playlist-organizer.md)** - Add DragOverlay component with drag state tracking, performance optimization, and robust cleanup

## Success Criteria

End-to-end verification that all drag operations work with visual feedback:

### Setup
1. Run `music-minion --web`
2. Navigate to any playlist organizer page
3. Ensure you have:
   - Multiple unassigned tracks
   - At least 3 buckets with tracks assigned to them
4. Open browser console (F12) to monitor for errors

### Test Cases

**✅ Unassigned Track Dragging:**
- Grab an unassigned track → see preview box following cursor
- Hover over bucket header → bucket highlights
- Drop on bucket → track assigns, preview disappears
- No console errors

**✅ Bucket-to-Bucket Dragging:**
- Grab track from Bucket A → see preview with bucket emoji + title
- Move cursor outside bucket → preview remains visible
- Hover over Bucket B → Bucket B highlights
- Drop on Bucket B → track moves, appears in Bucket B, removed from Bucket A

**✅ Bucket-to-Unassigned:**
- Grab track from bucket → see preview
- Hover over unassigned area → shows ring highlight
- Drop on unassigned → track returns to unassigned, bucket emoji removed

**✅ Within-Bucket Reordering (no regression):**
- Drag track within same bucket → reorders smoothly
- Preview visible during drag

**✅ Edge Cases:**
- Press Escape during drag → cancels, preview disappears
- Drop on invalid area → track returns to origin
- Rapid successive drags → smooth, no lag or errors

## Dependencies

**Existing:**
- `@dnd-kit/core` v6.3.1 (already installed)
- Nested DndContext architecture in Bucket.tsx (preserved)
- Existing drag handlers in PlaylistOrganizer.tsx

**No new dependencies required** - all components already available in @dnd-kit/core.

## Design Rationale

**Why DragOverlay?**
- Provides visual feedback across all contexts (including nested ones)
- Renders via portal, appearing above all elements
- Standard @dnd-kit pattern for multi-context drag operations

**Why not remove nested DndContext?**
- Within-bucket reordering requires SortableContext + nested DndContext
- Removing it would break existing functionality
- DragOverlay works harmoniously with nested contexts

## Implementation Notes

- Use `dropAnimation={null}` for instant feedback
- Keep preview simple (just track title/emoji, no complex components)
- State cleanup in both `onDragEnd` and `onDragCancel` prevents stuck states
- Preview styled to look "lifted" (shadow, slight opacity)
