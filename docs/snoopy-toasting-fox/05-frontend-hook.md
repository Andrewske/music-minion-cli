---
task: 05-frontend-hook
status: pending
depends: [04-frontend-types-api]
files:
  - path: web/frontend/src/hooks/usePlaylistOrganizer.ts
    action: modify
---

# Frontend Hook: Multi-bucket Mutations and Link Support

## Context
Core changes to the organizer hook to support tracks in multiple buckets and bucket linking. This is a critical change that affects the fundamental behavior of track assignment.

## Files to Modify/Create
- web/frontend/src/hooks/usePlaylistOrganizer.ts (modify)

## Implementation Details

### Add linkBucket mutation:

```typescript
const linkBucketMutation = useMutation({
  mutationFn: (params: { bucketId: string; playlistId: number | null }) => {
    return bucketsApi.linkBucket(params.bucketId, params.playlistId);
  },
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey });
  },
});

const linkBucket = useCallback(
  async (bucketId: string, playlistId: number | null): Promise<void> => {
    await linkBucketMutation.mutateAsync({ bucketId, playlistId });
  },
  [linkBucketMutation]
);
```

### Update assignTrackMutation optimistic update:

**REMOVE** the logic that removes track from other buckets:

```typescript
// BEFORE (remove this):
const updatedBuckets = previousSession.buckets.map((bucket) => {
  if (bucket.id === bucketId) {
    if (!bucket.track_ids.includes(trackId)) {
      return { ...bucket, track_ids: [...bucket.track_ids, trackId] };
    }
    return bucket;
  }
  // Remove track from other buckets  <-- REMOVE THIS PART
  return { ...bucket, track_ids: bucket.track_ids.filter((id) => id !== trackId) };
});

// AFTER:
const updatedBuckets = previousSession.buckets.map((bucket) => {
  if (bucket.id === bucketId && !bucket.track_ids.includes(trackId)) {
    return { ...bucket, track_ids: [...bucket.track_ids, trackId] };
  }
  return bucket;  // Keep all other buckets unchanged
});
```

### Update unassignTrackMutation optimistic update:

**FIX** the logic to only add to unassigned if track is not in ANY other bucket:

```typescript
// BEFORE (broken for multi-bucket):
const updatedUnassigned = previousSession.unassigned_track_ids.includes(trackId)
  ? previousSession.unassigned_track_ids
  : [...previousSession.unassigned_track_ids, trackId];

// AFTER:
const stillInOtherBucket = updatedBuckets.some(
  (b) => b.id !== bucketId && b.track_ids.includes(trackId)
);
const updatedUnassigned = stillInOtherBucket
  ? previousSession.unassigned_track_ids
  : previousSession.unassigned_track_ids.includes(trackId)
    ? previousSession.unassigned_track_ids
    : [...previousSession.unassigned_track_ids, trackId];
```

### Update return type to include linkBucket:

```typescript
return {
  // ... existing
  linkBucket,
  isLinking: linkBucketMutation.isPending,
};
```

### Update UsePlaylistOrganizerReturn interface:

```typescript
interface UsePlaylistOrganizerReturn {
  // ... existing
  linkBucket: (bucketId: string, playlistId: number | null) => Promise<void>;
  isLinking: boolean;
}
```

## Verification

1. TypeScript compiles: `cd web/frontend && pnpm tsc --noEmit`
2. Run app and verify:
   - Assigning a track to bucket A, then to bucket B, keeps the track in BOTH buckets
   - Track appears in both bucket track lists
3. Manual test of linkBucket (requires UI from later task, or test via browser console):
   ```javascript
   // In browser console when organizer is loaded
   const { linkBucket } = window.__organizerHook__;  // If exposed for debugging
   await linkBucket('bucket-id', 123);
   ```
