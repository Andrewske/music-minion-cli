# Fix Playlist Organizer: Keyboard Shortcuts + Drag-and-Drop

## Overview
Fix two critical usability issues in the Music Minion playlist organizer:

1. **Broken keyboard shortcuts**: Shift+number shortcuts for assigning tracks to buckets don't work because the browser reports shifted characters ("!", "@") instead of numbers
2. **Missing drag-and-drop**: Add intuitive drag-and-drop functionality to assign tracks from the unassigned table to buckets

The implementation extends the existing @dnd-kit setup (already used for within-bucket reordering) to support cross-component dragging while preserving all existing functionality.

## Task Sequence

1. **[01-fix-keyboard-shortcuts.md](./01-fix-keyboard-shortcuts.md)** - Fix Shift+number keyboard shortcuts by using `e.code` instead of `e.key`
   - Single-line change in PlaylistOrganizer.tsx
   - Immediately testable and verifiable
   - No dependencies

2. **[02-add-dnd-context-to-playlist-organizer.md](./02-add-dnd-context-to-playlist-organizer.md)** - Lift DndContext to PlaylistOrganizer level
   - Enables cross-component drag-and-drop
   - Adds sensors and drag routing logic
   - Sets up architecture for tasks 3 and 4

3. **[03-make-unassigned-tracks-draggable.md](./03-make-unassigned-tracks-draggable.md)** - Add drag handles to unassigned track table
   - Creates DraggableRow component
   - Integrates with virtualized table
   - Preserves click-to-play functionality

4. **[04-make-buckets-droppable.md](./04-make-buckets-droppable.md)** - Make bucket headers accept dropped tracks
   - Adds drop zone highlighting
   - Implements auto-expand on hover
   - Preserves within-bucket reordering

## Success Criteria

### Keyboard Shortcuts (End-to-End)
1. Start web mode: `music-minion --web`
2. Navigate to any playlist organizer
3. Create at least 3 buckets
4. Click an unassigned track to play it
5. Press **Shift+1** → Track assigns to first bucket, next track auto-plays
6. Press **Shift+2** → Track assigns to second bucket, advances
7. Continue through Shift+3, Shift+4, etc.
8. All shortcuts should work reliably and consistently

### Drag-and-Drop (End-to-End)
1. In playlist organizer with unassigned tracks
2. Grab drag handle (GripVertical icon) on any unassigned track
3. Drag over bucket header → Header highlights with accent color
4. Hold over collapsed bucket for 500ms → Bucket auto-expands
5. Drop on bucket → Track disappears from unassigned, appears in bucket, next track plays
6. Repeat for multiple tracks
7. All drags should be smooth and intuitive

### Regression Testing
- **Within-bucket reordering**: Drag tracks within expanded buckets → Still works
- **Bucket controls**: Up/down arrows, shuffle, edit, delete → All functional
- **Click-to-play**: Click unassigned tracks (not drag handle) → Plays track
- **Virtual scrolling**: Performance with 100+ tracks → No lag
- **Mobile**: Touch drag on phone/tablet → Works without scrolling issues

### Edge Cases
- Dragging when no buckets exist → No crash, graceful no-op
- Keyboard shortcut when no buckets → No crash, no-op
- Dragging currently playing track → Works, auto-advances
- Rapid consecutive operations (keyboard + drag) → Both complete successfully

## Dependencies

### Required Libraries (Already Installed)
- `@dnd-kit/core` ^6.3.1 - Core drag-and-drop functionality
- `@dnd-kit/sortable` ^10.0.0 - Sortable list utilities
- `@dnd-kit/utilities` ^3.2.2 - Transform utilities
- `lucide-react` ^0.564.0 - GripVertical icon component

### New Dependencies (Requires Installation)
- `react-toastify` - Toast notifications for error feedback

### Setup Instructions

**Before starting implementation**, install and configure react-toastify:

1. Install the package:
   ```bash
   cd web/frontend
   npm install react-toastify
   ```

2. Add ToastContainer to the app root (`web/frontend/src/routes/__root.tsx`):
   ```typescript
   import { ToastContainer } from 'react-toastify';
   import 'react-toastify/dist/ReactToastify.css';

   // In the component's return:
   <>
     <Outlet />
     <ToastContainer
       position="bottom-right"
       autoClose={3000}
       hideProgressBar={false}
       theme="dark"
     />
   </>
   ```

3. Verify toast system works by temporarily adding `toast.success('Setup complete!')` and checking the UI.

### Runtime Requirements
- Music Minion web mode: `music-minion --web`
- Browser with JavaScript enabled
- Test playlist with unassigned tracks

## Architecture Overview

### Before (Existing)
```
Bucket.tsx
└── DndContext (local)
    └── SortableContext
        └── SortableTrack (within-bucket reordering)
```

### After (New)
```
PlaylistOrganizer.tsx
└── DndContext (parent)             ← NEW: handles cross-component
    ├── UnassignedTrackTable
    │   └── DraggableRow            ← NEW: useDraggable
    │       └── GripVertical icon   ← NEW: drag handle
    └── Bucket
        ├── useDroppable            ← NEW: header drop zone
        └── DndContext (child)      ← KEPT: within-bucket reordering
            └── SortableContext
                └── SortableTrack
```

**Key Pattern**: Nested DndContexts with type-based routing
- Parent context handles `"unassigned-track"` type (cross-component)
- Child context handles `"bucket-track"` type (within-bucket)

## Implementation Notes

### Functional Programming Patterns
- Pure functions for transform calculations
- No mutation of drag state
- Immutable data flow via React Query

### Performance Considerations
- 8px activation constraint prevents accidental drags during scrolling
- Virtual scrolling maintained for unassigned table (handles 1000+ tracks)
- Memoized calculations for drag transforms
- Optimistic updates via React Query prevent UI lag

### Browser Compatibility
- `e.code` API: Supported in all modern browsers (Chrome 48+, Firefox 38+, Safari 10.1+)
- @dnd-kit: Works across desktop and touch devices
- No IE11 support (Music Minion already requires modern browser)

### Accessibility
- Drag handles are keyboard-navigable (Tab to focus, Space to grab/drop, Arrow keys to move)
- Semantic HTML with ARIA labels for screen readers
- Focus indicators for keyboard navigation

## Plan Review Improvements

The following enhancements were added during technical review:

1. **Numpad support** (Task 01): Keyboard shortcuts now work with both main number row and numpad
2. **Drop target validation** (Task 02): Validates that drops target actual buckets, prevents API errors
3. **Error handling** (Task 02): Try/catch with toast notifications for failed assignments
4. **Code deduplication** (Task 02): Extracted auto-advance logic into shared `playNextUnassignedTrack` function
5. **Column filtering** (Task 03): Filters cells by ID instead of position for robustness
6. **Keyboard accessibility** (Task 03): Drag handles are focusable with ARIA labels and focus styles
7. **useEffect deps** (Task 04): Added `setIsExpanded` to dependency array for exhaustive-deps compliance
8. **Type-based validation** (Task 04): Bucket drop zones tagged with `type: 'bucket'` for validation
