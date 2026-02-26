# Drag-and-Drop "Maximum Update Depth Exceeded" Error - Debug Log

## Problem Summary

**Error**: `Maximum update depth exceeded` when dragging unassigned tracks in `/playlist-organizer/{playlistId}`

**Symptoms**:
- Error occurs **immediately on drag start** (mouse down + move)
- Only affects **unassigned tracks** - bucket-to-bucket drags work fine
- Error originates from `measureRect` function in @dnd-kit during layout effects
- React component tree shows error in `<DndContext2>` component

**Stack Trace**:
```
at measureRect (chunk-NVYN7M2F.js:1903:5)
at commitHookEffectListMount (chunk-WERSD76P.js:16915:34)
The above error occurred in the <DndContext2> component:
```

## Environment

- **Framework**: React with TanStack Router
- **Drag-and-drop**: @dnd-kit/core + @dnd-kit/sortable
- **Virtual scrolling**: @tanstack/react-virtual
- **Table**: @tanstack/react-table
- **Platform**: Vite dev server (localhost:5173)

## Component Architecture

```
__root.tsx (Root Layout)
├── Sidebar
│   └── SidebarPlaylists (has conditional DndContext)
└── <Outlet>
    └── /playlist-organizer/$playlistId
        └── PlaylistOrganizer (has DndContext)
            ├── DragOverlay
            ├── UnassignedTrackTable (uses TanStack Table + Virtual Scrolling)
            │   └── DraggableRow (useDraggable hook)
            └── BucketList
                └── BucketComponent (useDroppable + SortableContext)
                    └── SortableTrack (useSortable hook)
```

## Attempted Fixes (In Order)

### Fix #1: Remove Nested DndContext from Bucket Component
**Commit**: `a1c2bcf`

**Hypothesis**: Nested DndContext (parent in PlaylistOrganizer, child in Bucket) was causing conflicts

**Changes**:
- Removed `DndContext` wrapper from Bucket.tsx
- Kept only `SortableContext` (which is safe to nest)
- Moved within-bucket reordering logic to parent's handleDragEnd
- Removed sensors and collision detection from Bucket

**Result**: ❌ Error persisted

**Learning**: The nested context in Bucket wasn't the issue since bucket drags work fine

---

### Fix #2: Add Drag Operation Locking
**Commit**: `6763114`

**Hypothesis**: Concurrent drag operations were causing state conflicts

**Changes**:
- Added `isDragOperationInProgress` ref to prevent concurrent drags
- Moved `setActiveId(null)` and `setActiveDragType(null)` to START of handleDragEnd
- Wrapped entire handleDragEnd in try-finally to ensure lock release

**Result**: ❌ Error persisted

**Learning**: The issue isn't concurrent operations - it happens on the first drag attempt

---

### Fix #3: Disable Sidebar DndContext on Organizer Page
**Commit**: `db6152d`

**Hypothesis**: Sidebar's DndContext (for playlist reordering) was nesting with organizer's context

**Changes**:
```tsx
// SidebarPlaylists.tsx line 184
{pinnedPlaylists.length > 0 && (
  isOnOrganizer ? (
    // Render static items without DndContext
    pinnedPlaylists.map(playlist => (
      <PlaylistItem key={playlist.id} playlist={playlist} isPinned={true} />
    ))
  ) : (
    // Normal drag-enabled rendering
    <DndContext sensors={sensors} ...>
```

**Result**: ❌ Error persisted

**Learning**: While this is good practice, the sidebar context wasn't causing the unassigned track issue

---

### Fix #4: Remove Drag Transform from DraggableRow
**Commit**: `6b96fcd`

**Hypothesis**: Applying both virtual scrolling transform AND drag transform to the original row was causing conflicts

**Changes**:
```tsx
// BEFORE:
const dragTransform = transform ? `translate3d(${transform.x}px, ${transform.y}px, 0)` : '';
const virtualTransform = `translateY(${virtualRow.start}px)`;
const combinedTransform = transform ? dragTransform : virtualTransform;
style={{ transform: combinedTransform, opacity: isDragging ? 0.5 : 1 }}

// AFTER:
const virtualTransform = `translateY(${virtualRow.start}px)`;
style={{ transform: virtualTransform, opacity: isDragging ? 0 : 1 }}
```

**Result**: ❌ Error persisted

**Learning**: Following @dnd-kit DragOverlay pattern correctly is important, but wasn't the root cause

---

### Fix #5: Memoize Table Columns and Helper Function
**Commit**: `fa9a4b4`

**Hypothesis**: Creating new `columns` array and `getColumnFlex` function on every render was causing TanStack Table + Virtual Scrolling to fully recalculate, creating layout effect conflicts

**Changes**:
```tsx
// Added imports
import { useMemo, useCallback } from 'react';

// Wrapped columns
const columns = useMemo(() => [
  // ... column definitions
], []);

// Wrapped getColumnFlex
const getColumnFlex = useCallback((column) => {
  // ... logic
}, []);
```

**Result**: ❌ Error persisted

**Learning**: While this is a performance optimization, it didn't solve the infinite loop

---

## Diagnostic Information

### What Works
✅ Dragging tracks between buckets
✅ Dragging tracks within same bucket to reorder
✅ Dragging bucket tracks back to unassigned area
✅ All drag operations that DON'T start from UnassignedTrackTable

### What Fails
❌ Dragging unassigned tracks to any bucket
❌ Any drag operation starting from UnassignedTrackTable
❌ Fails immediately on drag start (not during drag or on drop)

### Error Pattern
```
1. User clicks and starts dragging unassigned track
2. handleDragStart fires → sets activeId and activeDragType state
3. measureRect (from @dnd-kit) fires during layout effects
4. React detects nested state updates
5. "Maximum update depth exceeded" error thrown
6. Drag operation aborts
```

### Key Observations
1. **Only affects UnassignedTrackTable**: Bucket components work fine
2. **Immediate failure**: Error on drag start, not during movement
3. **measureRect involvement**: @dnd-kit's measurement hook is in the stack
4. **Layout effects conflict**: Multiple layout effects trying to update state
5. **DndContext2 in error**: React shows error in second DndContext despite fixes

## Component Differences

### UnassignedTrackTable (FAILS)
- Uses `useDraggable` hook
- Uses TanStack Table for column management
- Uses TanStack Virtual for virtual scrolling
- Renders ~100+ rows with absolute positioning
- Complex render tree with table/tbody/tr structure
- Has droppable area at container level

### Bucket SortableTrack (WORKS)
- Uses `useSortable` hook
- Simple component with GripVertical icon
- No virtual scrolling
- No table structure
- Lives inside SortableContext

## Remaining Possibilities

### 1. Virtual Scrolling + useDraggable Incompatibility
**Theory**: The combination of absolute positioning from virtual scrolling + drag measurements may be incompatible

**Test**: Try removing virtual scrolling temporarily:
```tsx
// Comment out virtualizer
// const virtualizer = useVirtualizer({ ... });

// Render all rows normally
{tracks.map(track => (
  <DraggableRow key={track.id} track={track} ... />
))}
```

### 2. Table Structure Interference
**Theory**: The table/tbody/tr DOM structure may interfere with @dnd-kit's measurements

**Test**: Try rendering tracks as divs instead of table elements:
```tsx
// Change from <tr> to <div role="row">
// Change from <td> to <div role="cell">
```

### 3. Multiple useDroppable/useDraggable in Same Hierarchy
**Theory**: UnassignedTrackTable has BOTH:
- `useDroppable` at container level (line 29)
- `useDraggable` in each row (line 128)

This might create measurement conflicts.

**Test**: Try removing the droppable container temporarily

### 4. Sensor Configuration
**Theory**: PointerSensor might be firing too early with virtual scrolling

**Test**: Try different sensor settings:
```tsx
useSensor(PointerSensor, {
  activationConstraint: {
    distance: 15,  // Increase from 8
    delay: 100,    // Add delay
  },
})
```

### 5. React.StrictMode
**Theory**: Development mode's double-rendering might be causing issues with effects

**Test**: Check if React.StrictMode is enabled in main.tsx and try disabling

### 6. @dnd-kit Version Compatibility
**Theory**: There might be a bug in the specific version being used

**Test**: Check package.json versions and try updating/downgrading:
```json
"@dnd-kit/core": "^?",
"@dnd-kit/sortable": "^?",
"@dnd-kit/utilities": "^?"
```

### 7. Table Cell Flex Layout + Drag
**Theory**: The flex layout with dynamic column widths might be causing reflows during drag

**Test**: Try fixed pixel widths temporarily instead of flex

### 8. Hidden Root Cause in handleDragStart
**Theory**: Something in PlaylistOrganizer's handleDragStart is triggering cascading updates

**Test**: Add console logs to track exact state update sequence:
```tsx
const handleDragStart = useCallback((event: DragStartEvent) => {
  console.log('🔴 handleDragStart called', event.active.id);
  setActiveId(active.id as number);
  console.log('🔴 activeId set');
  setActiveDragType(active.data.current?.type as 'unassigned-track' | 'bucket-track');
  console.log('🔴 activeDragType set');
}, []);
```

## Files to Investigate

### Current State of Critical Files

**UnassignedTrackTable.tsx** (src/components/organizer/UnassignedTrackTable.tsx):
- Lines 1-2: Uses useMemo, useCallback (recently added)
- Lines 29-32: useDroppable for container
- Lines 36-91: Memoized columns array
- Lines 94-102: Memoized getColumnFlex
- Lines 111-116: useVirtualizer configuration
- Lines 128-131: useDraggable in each DraggableRow
- Lines 147-153: Row style with virtual transform only

**PlaylistOrganizer.tsx** (src/pages/PlaylistOrganizer.tsx):
- Lines 110-114: handleDragStart sets activeId and activeDragType
- Lines 116-119: handleDragCancel clears state
- Lines 164-321: handleDragEnd with locking and cleanup
- Lines 399-405: DndContext configuration
- Lines 473-481: DragOverlay component

**SidebarPlaylists.tsx** (src/components/sidebar/SidebarPlaylists.tsx):
- Lines 42: isOnOrganizer check
- Lines 184-197: Conditional DndContext (disabled on organizer)

## Next Steps for Debugging

### ⚠️ HIGHEST PRIORITY TEST - Disable React.StrictMode

React.StrictMode intentionally **double-invokes** effects in development to catch bugs. This could be causing `measureRect` to fire twice, creating the infinite loop.

**Test**: Edit `src/main.tsx`:

```tsx
// BEFORE (current):
<StrictMode>
  <RouterProvider router={router} />
</StrictMode>

// AFTER (test):
<RouterProvider router={router} />
```

**Expected outcome**: If this fixes it, the issue is StrictMode's double-invocation conflicting with @dnd-kit's measurements.

**If it works**: You can either:
- Leave StrictMode disabled (acceptable for development)
- Use a more defensive pattern in measurements
- Report the issue to @dnd-kit maintainers

---

### Other Immediate Actions
1. ~~**Check package versions**~~: ✅ Done (see Known Facts)
2. **Enable verbose logging**: Add console.logs throughout drag lifecycle
3. **Test without virtual scrolling**: Comment out virtualizer temporarily
4. **Test with simple div structure**: Replace table elements with divs
5. **Check browser DevTools**: Use React DevTools to inspect component re-renders

### Alternative Approaches

If all debugging fails, consider:

1. **Rewrite UnassignedTrackTable without virtual scrolling**
   - Use simple list rendering
   - Add pagination if needed for performance
   - Simpler = fewer moving parts

2. **Use react-beautiful-dnd instead of @dnd-kit**
   - Different library might not have same issues
   - Has built-in virtual scrolling support

3. **Split UnassignedTrackTable into simpler components**
   - Separate table from drag-and-drop
   - Use portals for dragged items
   - More control over rendering

4. **Use native HTML5 drag-and-drop**
   - Browser-native, fewer React integration issues
   - More manual but more predictable

## Known Facts

### Package Versions
```json
"@dnd-kit/core": "^6.3.1"
"@dnd-kit/sortable": "^10.0.0"
"@dnd-kit/utilities": "^3.2.2"
```

### React Configuration
- **React.StrictMode**: ✅ **ENABLED** (src/main.tsx lines 8-11)
- This causes double-invocation of effects in development mode
- Could be amplifying the measureRect issue

## Questions to Answer

1. ~~What exact versions of @dnd-kit packages are installed?~~ **ANSWERED**: See above
2. ~~Is React.StrictMode enabled?~~ **ANSWERED**: YES
3. Does removing virtual scrolling fix the issue?
4. Does changing table to div structure fix it?
5. What do React DevTools show during drag start?
6. Are there any console warnings before the error?
7. Does it work in production build vs dev build?
8. **Does disabling StrictMode fix the issue?** ⚠️ **HIGH PRIORITY TEST**

## Conclusion

Despite 5 different fixes addressing various aspects of the drag-and-drop system:
- Nested context removal
- Drag operation locking
- Sidebar context conditional rendering
- Proper DragOverlay pattern
- Performance memoization

The error persists, suggesting the root cause is deeper than initially suspected. The issue is specific to the UnassignedTrackTable component's combination of:
- Virtual scrolling (absolute positioning)
- Table structure (complex DOM)
- useDraggable hook
- useDroppable container

The next phase requires systematic elimination of these factors to isolate the true cause.

---

**Document created**: 2026-02-26
**Last updated**: After 5 attempted fixes
**Status**: Issue unresolved, investigation ongoing
