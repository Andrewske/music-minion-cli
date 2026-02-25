# Bucket-to-Bucket and Bucket-to-Unassigned Drag-and-Drop

## Overview

Extend the Music Minion playlist organizer drag-and-drop system to support two new capabilities:
1. **Drag tracks between buckets** (e.g., from Bucket A → Bucket B)
2. **Drag tracks from buckets back to unassigned**

This is a frontend-only implementation. All required backend APIs (`assignTrack`, `unassignTrack`) already exist with full optimistic update support.

**Scope**: Desktop-only drag-and-drop. Mobile users will continue using keyboard shortcuts (Shift+1-9) for bucket assignment. Mobile touch-based drag-and-drop is tracked in `docs/ideas.md` as a future enhancement.

### Current Architecture

The playlist organizer uses a nested DndContext architecture:
- **Parent** (PlaylistOrganizer): Handles cross-context operations with `pointerWithin` collision detection
- **Child** (Bucket): Handles within-bucket reordering with `closestCenter` collision detection

The parent context can detect when `'bucket-track'` drags leave their bucket's `SortableContext`. By extending the parent's `handleDragEnd` handler, we capture cross-bucket and bucket-to-unassigned drops.

## Task Sequence

1. **[01-update-bucket-drag-handlers.md](./01-update-bucket-drag-handlers.md)** - Add source bucket tracking to SortableTrack and update child handler
   - Modifies: `Bucket.tsx`
   - Adds `bucketId` prop to track drag data
   - Ensures child handler only processes same-bucket reordering

2. **[02-make-unassigned-area-droppable.md](./02-make-unassigned-area-droppable.md)** - Make unassigned track table accept dropped bucket tracks
   - Modifies: `UnassignedTrackTable.tsx`
   - Adds droppable zone with visual feedback
   - Provides drop target for bucket→unassigned operations

3. **[03-update-parent-drag-handler.md](./03-update-parent-drag-handler.md)** - Extend parent handler to route cross-bucket and bucket-to-unassigned drags
   - Modifies: `PlaylistOrganizer.tsx`
   - Adds handler cases for bucket-track drag type
   - Routes to `assignTrack()` or `unassignTrack()` based on drop target

4. **[04-extend-keyboard-shortcuts.md](./04-extend-keyboard-shortcuts.md)** - Extend Shift+1-9 shortcuts to support bucket-to-bucket moves
   - Modifies: `PlaylistOrganizer.tsx`
   - Updates keyboard handler to detect current bucket and move between buckets
   - Auto-advance only when moving from unassigned (not bucket→bucket)

**Note**: Tasks 01 and 02 can be implemented in parallel if desired (no technical dependency between them). However, completing Task 01 first makes testing Task 02's visual feedback easier, as you'll be able to drag bucket tracks to see the drop zone highlighting. Task 04 can be done in parallel with 01-03 or after, as it's independent.

## Success Criteria

### End-to-End Verification

1. **Start web mode**: `music-minion --web`
2. **Navigate to any playlist organizer** with unassigned tracks
3. **Create at least 3 buckets** and assign some tracks to them

#### Test: Unassigned → Bucket (Verify No Regression)
- Drag unassigned track to bucket header → assigns correctly
- Verify auto-advance plays next unassigned track
- Works with both collapsed and expanded buckets

#### Test: Bucket → Different Bucket (New Feature)
- Drag track from Bucket A to Bucket B header → track moves
- Verify track removed from source bucket
- Verify track appears at end of target bucket
- Test with collapsed target buckets
- Toast notification: "Track moved to bucket"

#### Test: Bucket → Unassigned (New Feature)
- Drag track from bucket to unassigned table → returns to unassigned
- Verify track removed from bucket
- Verify bucket emoji removed from track
- Drag currently playing track → playback continues
- Toast notification: "Track returned to unassigned"

#### Test: Within-Bucket Reordering (Verify No Regression)
- Drag track within same bucket → reorders correctly
- Verify smooth drag behavior with virtual scrolling
- No API calls made (check network tab)

#### Test: Edge Cases
- Drop on same bucket header → no-op (no API call, no toast)
- Drop outside valid targets → track returns to origin
- Disconnect network → error toast, UI reverts (optimistic update rollback)
- Rapid successive drags → no race conditions

### Visual Feedback

- **Bucket headers**: Highlight with `bg-obsidian-accent/20` when hovering with track
- **Unassigned area**: Shows `ring-2 ring-obsidian-accent` when hovering with bucket track
- **Dragged track**: 50% opacity during drag
- **Auto-expand**: Collapsed buckets expand after 500ms hover (existing behavior preserved)

### Optimistic Updates

- UI updates immediately on drop
- Reverts automatically if API call fails
- Toast notifications for success/errors
- No loading states needed (handled by existing React Query mutations)

## Dependencies

### Required Libraries (Already Installed)
- `@dnd-kit/core` - Core drag-and-drop functionality
- `@dnd-kit/sortable` - Sortable list utilities
- `react-toastify` - Toast notifications

### Runtime Requirements
- Music Minion web mode: `music-minion --web`
- Browser with JavaScript enabled
- Test playlist with unassigned tracks and buckets

## Design Rationale

**Why no auto-play on unassign?**
User is organizing tracks, not actively listening. Auto-advancing would interrupt their workflow.

**Why make entire unassigned container droppable?**
Larger drop target is easier to hit than just the header. More intuitive UX.

**Why check same-bucket in parent handler?**
Prevents no-op API calls and provides early exit for better performance.

**Why keep nested DndContext architecture?**
Preserves existing collision detection strategies that work well: `pointerWithin` for cross-context, `closestCenter` for precise within-bucket reordering.

## Architecture Notes

### Drag Type Routing
The system uses type-based routing to handle different drag scenarios:
- `'unassigned-track'` → Parent handles (existing)
- `'bucket-track'` → Parent handles cross-bucket/unassign, child handles same-bucket reordering
- `'bucket'` → Drop zone identifier for bucket headers
- `'unassigned-area'` → Drop zone identifier for unassigned table

### Handler Separation
- **Parent handler**: Cross-context operations (unassigned↔bucket, bucket↔bucket)
- **Child handler**: Single-context operations (within-bucket reordering)
- Child checks `sourceBucketId !== bucket.id` to avoid interfering with parent

**Collision Detection Strategy**: The parent's `pointerWithin` strategy triggers when the pointer enters a droppable zone (bucket headers, unassigned area), while the child's `closestCenter` triggers when near a track for precise reordering. This ensures the parent handles cross-context drops (larger target areas) and the child handles same-bucket reordering (precise positioning) without conflicts.

### API Contract
- `assignTrack(targetBucketId, trackId)` - Automatically removes from old bucket if present
- `unassignTrack(sourceBucketId, trackId)` - Returns track to unassigned, removes bucket emoji
- Both APIs have full optimistic update support in `usePlaylistOrganizer` hook
