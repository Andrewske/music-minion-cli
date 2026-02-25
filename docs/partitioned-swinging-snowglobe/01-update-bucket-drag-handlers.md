---
task: 01-update-bucket-drag-handlers
status: done
depends: []
files:
  - path: web/frontend/src/components/organizer/Bucket.tsx
    action: modify
---

# Update Bucket Drag Handlers

## Context

Enable cross-bucket dragging by adding source bucket tracking to SortableTrack and updating the child drag handler to only handle same-bucket reordering. This is the foundational change that allows the parent context to detect when bucket tracks are dragged outside their origin bucket.

## Files to Modify

- `web/frontend/src/components/organizer/Bucket.tsx` (modify)

## Implementation Details

### Change 1: Add Source Bucket Tracking to SortableTrack

**Location**: Lines 40-54 (SortableTrackProps interface and useSortable hook)

1. Add `bucketId: string` prop to `SortableTrackProps` interface:
   ```typescript
   interface SortableTrackProps {
     track: PlaylistTrackEntry;
     bucketId: string; // NEW: Source bucket for tracking
   }
   ```

2. Pass `bucketId` to `useSortable` data (line 53):
   ```typescript
   const { ... } = useSortable({
     id: track.id,
     data: {
       type: 'bucket-track',
       bucketId, // NEW: Include source bucket in drag data
     },
   });
   ```

3. Pass `bucket.id` when rendering SortableTrack (line 266):
   ```typescript
   <SortableTrack key={track.id} track={track} bucketId={bucket.id} />
   ```

**Why**: We need to know which bucket a track came from to call `unassignTrack(bucketId, trackId)` when dragging back to unassigned, and to prevent the child handler from interfering with cross-bucket drags.

### Change 3: Add Test IDs (Optional but Recommended)

**Location**: Line 150 (bucket header div with `ref={setDropRef}`)

Add `data-testid` attribute to the droppable bucket header for automated testing:

```typescript
<div
  ref={setDropRef}
  data-testid={`bucket-header-${bucket.id}`}
  className={...}
>
```

**Why**: Enables reliable automated testing (Playwright/Cypress) without brittle selectors.

### Optional Enhancement: Bucket Capacity Indicator

**Location**: Bucket header (collapsed state)

Consider adding track count display on collapsed buckets to help users see bucket sizes at a glance:

```typescript
{!isExpanded && tracks.length > 0 && (
  <span className="text-xs text-white/40 ml-2">
    {tracks.length} {tracks.length === 1 ? 'track' : 'tracks'}
  </span>
)}
```

**Why**: Helps users balance bucket sizes and quickly identify full/empty buckets during organizing.

### Change 2: Update Child Drag Handler

**Location**: Lines 125-136 (handleDragEnd function in BucketComponent)

Replace the `handleDragEnd` function with:

```typescript
const handleDragEnd = (event: DragEndEvent): void => {
  const { active, over } = event;

  if (!over) return;
  if (active.id === over.id) return;
  if (active.data.current?.type === 'unassigned-track') return;

  const sourceBucketId = active.data.current?.bucketId;
  if (sourceBucketId !== bucket.id) return; // NEW: Prevent cross-bucket handling

  const oldIndex = trackIds.indexOf(active.id as number);
  const newIndex = trackIds.indexOf(over.id as number);

  if (oldIndex === -1 || newIndex === -1) return;

  const newOrder = arrayMove(trackIds, oldIndex, newIndex);
  onReorderTracks(newOrder);
};
```

**Key addition**: The `if (sourceBucketId !== bucket.id) return;` line ensures the child handler only manages same-bucket reordering and doesn't interfere with the parent's cross-bucket handling.

**Why**: Without this check, the child handler might fire for cross-bucket drags if the user drops precisely on another track. This check ensures clean separation of concerns:
- Parent: Cross-context operations (unassigned↔bucket, bucket↔bucket)
- Child: Single-context operations (within-bucket reordering)

## Verification

1. Build TypeScript: `npx tsc --noEmit`
   - Should compile with no errors
   - Verify no type errors in Bucket.tsx

2. Start web mode: `music-minion --web`
   - Navigate to playlist organizer
   - Open browser console (F12)

3. Test within-bucket reordering still works:
   - Expand a bucket with multiple tracks
   - Drag a track to reorder within the same bucket
   - Verify the track reorders correctly
   - **IMPORTANT**: Open browser console (F12) and verify drag data shows `type: 'bucket-track'` and `bucketId: '<uuid>'` when dragging bucket tracks. This runtime check is critical - if `bucketId` is missing, Task 03 will fail with "Missing source bucket ID" errors.

4. Test collapsed bucket hover feedback:
   - Collapse a bucket
   - Drag a track over the collapsed bucket header
   - Verify: After 500ms, bucket auto-expands (existing behavior from lines 103-108)
   - Optional enhancement: Add visual pulse/glow to header during hover before expansion

5. Prepare for next task:
   - Cross-bucket dragging won't work yet (needs parent handler update in Task 03)
   - But console should show the drag data includes `bucketId`
