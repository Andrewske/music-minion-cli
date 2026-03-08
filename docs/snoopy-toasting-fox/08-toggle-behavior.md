---
task: 08-toggle-behavior
status: pending
depends: [05-frontend-hook]
files:
  - path: web/frontend/src/pages/PlaylistOrganizer.tsx
    action: modify
---

# UI: Toggle Behavior for Bucket Clicks

## Context
When clicking a bucket that already contains the current track, the track should be unassigned (removed) from that bucket instead of being added again. This creates a toggle behavior for bucket assignment.

## Files to Modify/Create
- web/frontend/src/pages/PlaylistOrganizer.tsx (modify)

## Implementation Details

### Modify `assignCurrentTrackToBucket`:

```typescript
// BEFORE:
const assignCurrentTrackToBucket = useCallback(
  async (bucketId: string): Promise<void> => {
    if (!currentTrack) return;

    const currentBucketId = trackToBucketMap.get(currentTrack.id);
    if (currentBucketId === bucketId) return;  // No-op if already in bucket

    try {
      await assignTrack(bucketId, currentTrack.id);
    } catch (error) {
      // ...
    }
  },
  [currentTrack, trackToBucketMap, assignTrack]
);

// AFTER:
const assignCurrentTrackToBucket = useCallback(
  async (bucketId: string): Promise<void> => {
    if (!currentTrack) return;

    // Check if track is already in this bucket
    const bucket = buckets.find(b => b.id === bucketId);
    const isInBucket = bucket?.track_ids.includes(currentTrack.id) ?? false;

    try {
      if (isInBucket) {
        // Toggle OFF: Unassign track from bucket
        await unassignTrack(bucketId, currentTrack.id);
      } else {
        // Toggle ON: Assign track to bucket
        await assignTrack(bucketId, currentTrack.id);
      }
    } catch (error) {
      console.error('Failed to toggle track assignment:', error);
      const message = error instanceof Error ? error.message : String(error);
      toast.error(`Failed to update track: ${message}`);
    }
  },
  [currentTrack, buckets, assignTrack, unassignTrack]
);
```

### Update trackToBucketMap to support multi-bucket:

Since a track can now be in multiple buckets, replace `trackToBucketMap` with `trackToBucketsMap` (Set-based):

```typescript
// REPLACE trackToBucketMap with:
const trackToBucketsMap = useMemo(() => {
  const map = new Map<number, Set<string>>();
  buckets.forEach((bucket) => {
    bucket.track_ids.forEach((trackId) => {
      if (!map.has(trackId)) {
        map.set(trackId, new Set());
      }
      map.get(trackId)!.add(bucket.id);
    });
  });
  return map;
}, [buckets]);

// Update activeBucketId to activeBucketIds (Set):
const activeBucketIds = currentTrack
  ? trackToBucketsMap.get(currentTrack.id) ?? new Set<string>()
  : new Set<string>();
```

### Update BucketList to highlight all containing buckets:

Pass `activeBucketIds: Set<string>` instead of `activeBucketId: string | null`:
- Each bucket header checks `activeBucketIds.has(bucket.id)` for highlight styling
- All buckets containing the current track are highlighted simultaneously

### Visual feedback:

- When track is in a bucket, that bucket header should have visual indicator (e.g., checkmark, different border)
- Clicking an "active" bucket should show it becoming "inactive"

## Verification

1. Start with a track NOT in any bucket
2. Click bucket A → track should be added to bucket A
3. Click bucket A again → track should be REMOVED from bucket A (back to unassigned)
4. Click bucket A, then click bucket B → track should be in BOTH buckets
5. Click bucket A when track is in both A and B → track removed from A, stays in B
6. Verify keyboard shortcuts (Shift+1-9) also follow toggle behavior
