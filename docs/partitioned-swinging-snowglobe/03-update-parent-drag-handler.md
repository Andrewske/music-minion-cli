---
task: 03-update-parent-drag-handler
status: done
depends: [01-update-bucket-drag-handlers, 02-make-unassigned-area-droppable]
files:
  - path: web/frontend/src/pages/PlaylistOrganizer.tsx
    action: modify
---

# Update Parent Drag Handler

## Context

Extend the parent DndContext handler to route cross-bucket and bucket-to-unassigned drag operations. This is the final piece that enables dragging tracks between buckets and back to unassigned status.

## Files to Modify

- `web/frontend/src/pages/PlaylistOrganizer.tsx` (modify)

## Implementation Details

### Change 1: Add unassignTrack to Hook Destructuring

**Location**: Line 35 (inside usePlaylistOrganizer destructuring)

Add `unassignTrack` to the destructured values:

```typescript
const {
  session,
  isLoading,
  buckets,
  unassignedTrackIds,
  assignTrack,
  unassignTrack, // ADD THIS
  applyOrder,
  getBucketByIndex,
  // ... rest unchanged
} = usePlaylistOrganizer({ playlistId });
```

### Change 2: Replace handleDragEnd Function

**Location**: Lines 95-118 (handleDragEnd function)

Replace the entire `handleDragEnd` function with:

```typescript
const handleDragEnd = async (event: DragEndEvent): Promise<void> => {
  const { active, over } = event;
  if (!over) return;

  const dragType = active.data.current?.type;

  // Case 1: Unassigned track → bucket (existing functionality)
  if (dragType === 'unassigned-track') {
    if (over.data.current?.type !== 'bucket') return;

    const trackId = active.id as number;
    const bucketId = over.id as string;

    // Type guard for development
    if (typeof trackId !== 'number' || typeof bucketId !== 'string') {
      console.error('Invalid drag data types:', { trackId, bucketId });
      return;
    }

    try {
      await assignTrack(bucketId, trackId);
      playNextUnassignedTrack(trackId);
    } catch (error) {
      console.error('Failed to assign track:', error);
      toast.error(`Failed to assign track ${trackId} to bucket ${bucketId}: ${error.message}`);
    }
    return;
  }

  // Case 2: Bucket track → different bucket OR unassigned (NEW)
  if (dragType === 'bucket-track') {
    const trackId = active.id as number;
    const sourceBucketId = active.data.current?.bucketId as string | undefined;

    // Type guards for development
    if (typeof trackId !== 'number') {
      console.error('Invalid track ID type:', trackId);
      return;
    }

    if (!sourceBucketId || typeof sourceBucketId !== 'string') {
      console.error('Missing or invalid source bucket ID in drag data:', sourceBucketId);
      return;
    }

    const overType = over.data.current?.type;

    // Case 2a: Bucket track → different bucket
    if (overType === 'bucket') {
      const targetBucketId = over.id as string;

      if (typeof targetBucketId !== 'string') {
        console.error('Invalid target bucket ID type:', targetBucketId);
        return;
      }

      // No-op if dropping on same bucket
      if (targetBucketId === sourceBucketId) return;

      try {
        await assignTrack(targetBucketId, trackId);
      } catch (error) {
        console.error('Failed to move track between buckets:', error);
        toast.error(`Failed to move track ${trackId} from bucket ${sourceBucketId} to ${targetBucketId}: ${error.message}`);
      }
      return;
    }

    // Case 2b: Bucket track → unassigned area
    if (overType === 'unassigned-area') {
      try {
        await unassignTrack(sourceBucketId, trackId);
      } catch (error) {
        console.error('Failed to unassign track:', error);
        toast.error(`Failed to unassign track ${trackId} from bucket ${sourceBucketId}: ${error.message}`);
      }
      return;
    }

    // Case 2c: Bucket track → track in different bucket (NEW)
    if (overType === 'bucket-track') {
      const targetBucketId = over.data.current?.bucketId as string | undefined;

      if (!targetBucketId || typeof targetBucketId !== 'string') {
        console.error('Missing or invalid target bucket ID in drag data:', targetBucketId);
        return;
      }

      // No-op if dropping in same bucket (within-bucket reordering handled by child)
      if (targetBucketId === sourceBucketId) return;

      try {
        await assignTrack(targetBucketId, trackId);
      } catch (error) {
        console.error('Failed to move track between buckets:', error);
        toast.error(`Failed to move track ${trackId} from bucket ${sourceBucketId} to ${targetBucketId}: ${error.message}`);
      }
      return;
    }
  }
};
```

### Design Decisions Explained

**No auto-play on unassign**: User is organizing tracks, not actively listening. Auto-advancing would interrupt their workflow.

**Same-bucket drops are no-ops**: The `targetBucketId === sourceBucketId` check prevents unnecessary API calls. Within-bucket reordering is handled by the child handler.

**Track-to-track drops append to end**: When dropping on a track in a different bucket (Case 2c), the track is appended to the end of the target bucket rather than inserted at the drop position. This simplifies implementation (no positional insertion API needed) and can be extended later if needed. Users can reorder within buckets after moving.

**Error toasts only**: Success is indicated by optimistic UI updates (track visibly moves). Error toasts provide descriptive debugging info (track ID, bucket IDs, error message) for troubleshooting API failures.

**Explicit returns**: Makes control flow obvious and prevents fall-through bugs.

**Type guards**: Runtime validation of drag data types catches implementation errors during development (e.g., missing `bucketId` prop in Task 01, wrong ID types). These checks are defensive - TypeScript can't validate `active.id` or `over.id` types at compile time since they come from the dnd-kit library as generic IDs.

## Verification

1. Build TypeScript: `npx tsc --noEmit`
   - Should compile with no errors

2. Start web mode: `music-minion --web`
   - Navigate to playlist organizer
   - Create at least 3 buckets with some tracks

3. **Test Bucket → Different Bucket (Header Drop)**:
   - Expand Bucket A with tracks
   - Drag a track from Bucket A by its handle
   - Drop on Bucket B's header (can be collapsed or expanded)
   - **Expected**:
     - Track disappears from Bucket A
     - Track appears at end of Bucket B
     - No toast notification (success indicated by visual change)
     - If you expand Bucket B, the track is visible at the bottom

3a. **Test Bucket → Different Bucket (Track Drop)**:
   - Expand both Bucket A and Bucket B with tracks
   - Drag a track from Bucket A by its handle
   - Drop on any track within Bucket B
   - **Expected**:
     - Track disappears from Bucket A
     - Track appears at end of Bucket B (appends, not at drop position)
     - No toast notification (success indicated by visual change)

4. **Test Bucket → Unassigned**:
   - Drag a track from any bucket
   - Drop on the unassigned table area
   - **Expected**:
     - Track disappears from bucket
     - Track appears in unassigned table
     - No toast notification (success indicated by visual change)
     - Bucket emoji removed from track metadata

5. **Test Same-Bucket Drop (No-op)**:
   - Drag a track from Bucket A
   - Drop on Bucket A's header
   - **Expected**: No API call, no toast, track stays in place

6. **Test Existing Functionality (No Regression)**:
   - Drag unassigned track to bucket → should still work with auto-advance
   - Drag track within same bucket to reorder → should still work smoothly
   - Keyboard shortcuts (Shift+1 through Shift+9) → should still assign tracks

7. **Test Error Handling**:
   - Disconnect network (browser dev tools)
   - Try dragging track between buckets
   - **Expected**: Error toast with detailed message (track ID, bucket IDs, error), UI reverts to original state (optimistic update rollback)
   - **Optional enhancement**: If rollback takes >500ms, show subtle loading indicator on affected track/bucket

8. **Test Edge Cases**:
   - Drag currently playing track to unassigned → playback continues
   - Drag track to collapsed bucket → works, track appears when expanded
   - Rapid successive drags → no race conditions, all operations complete
