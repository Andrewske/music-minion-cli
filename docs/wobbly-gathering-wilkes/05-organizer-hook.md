---
task: 05-organizer-hook
status: pending
depends: [04-frontend-api-client]
files:
  - path: web/frontend/src/hooks/usePlaylistOrganizer.ts
    action: create
---

# React Query Hook for Playlist Organizer

## Context
Create a custom hook that manages bucket session state with React Query, similar to usePlaylistBuilder pattern. Handles data fetching, mutations, and optimistic updates.

## Files to Modify/Create
- web/frontend/src/hooks/usePlaylistOrganizer.ts (new)

## Implementation Details

```typescript
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as bucketsApi from '../api/buckets';
import type { BucketSession, Bucket } from '../api/buckets';

interface UsePlaylistOrganizerOptions {
  playlistId: number;
  enabled?: boolean;
}

interface UsePlaylistOrganizerReturn {
  // Session data
  session: BucketSession | undefined;
  isLoading: boolean;
  error: Error | null;

  // Bucket operations
  createBucket: (name: string, emojiId?: string) => Promise<Bucket>;
  updateBucket: (bucketId: string, updates: { name?: string; emoji_id?: string | null }) => Promise<void>;
  deleteBucket: (bucketId: string) => Promise<void>;
  moveBucket: (bucketId: string, direction: 'up' | 'down') => Promise<void>;
  shuffleBucket: (bucketId: string) => Promise<void>;

  // Track operations
  assignTrack: (bucketId: string, trackId: number) => Promise<void>;
  unassignTrack: (bucketId: string, trackId: number) => Promise<void>;
  reorderTracks: (bucketId: string, trackIds: number[]) => Promise<void>;

  // Session operations
  applyOrder: () => Promise<void>;
  discardSession: () => Promise<void>;

  // Computed
  buckets: Bucket[];
  unassignedTrackIds: number[];
  getBucketByIndex: (index: number) => Bucket | undefined;

  // Loading states (for UI feedback)
  isAssigning: boolean;
  isApplying: boolean;
}

export function usePlaylistOrganizer({
  playlistId,
  enabled = true,
}: UsePlaylistOrganizerOptions): UsePlaylistOrganizerReturn {
  const queryClient = useQueryClient();
  const queryKey = ['organizer', 'session', playlistId];

  // Main query - creates or resumes session
  const { data: session, isLoading, error } = useQuery({
    queryKey,
    queryFn: () => bucketsApi.createOrResumeSession(playlistId),
    enabled,
    staleTime: 1000 * 60 * 5, // 5 minutes
  });

  // Invalidation helper
  const invalidate = () => queryClient.invalidateQueries({ queryKey });

  // Bucket mutations
  const createBucketMutation = useMutation({
    mutationFn: ({ name, emojiId }: { name: string; emojiId?: string }) =>
      bucketsApi.createBucket(session!.id, { name, emoji_id: emojiId }),
    onSuccess: invalidate,
  });

  const updateBucketMutation = useMutation({
    mutationFn: ({ bucketId, updates }: { bucketId: string; updates: { name?: string; emoji_id?: string | null } }) =>
      bucketsApi.updateBucket(bucketId, updates),
    onSuccess: invalidate,
  });

  const deleteBucketMutation = useMutation({
    mutationFn: bucketsApi.deleteBucket,
    onSuccess: invalidate,
  });

  const moveBucketMutation = useMutation({
    mutationFn: ({ bucketId, direction }: { bucketId: string; direction: 'up' | 'down' }) =>
      bucketsApi.moveBucket(bucketId, direction),
    onSuccess: invalidate,
  });

  const shuffleBucketMutation = useMutation({
    mutationFn: bucketsApi.shuffleBucket,
    onSuccess: invalidate,
  });

  // Track mutations with optimistic updates for responsive keyboard shortcuts
  const assignTrackMutation = useMutation({
    mutationFn: ({ bucketId, trackId }: { bucketId: string; trackId: number }) =>
      bucketsApi.assignTrack(bucketId, trackId),
    onMutate: async ({ bucketId, trackId }) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey });

      // Snapshot previous value
      const previousSession = queryClient.getQueryData<BucketSession>(queryKey);

      // Optimistically update
      if (previousSession) {
        queryClient.setQueryData<BucketSession>(queryKey, {
          ...previousSession,
          unassigned_track_ids: previousSession.unassigned_track_ids.filter((id) => id !== trackId),
          buckets: previousSession.buckets.map((b) =>
            b.id === bucketId
              ? { ...b, track_ids: [...b.track_ids, trackId] }
              : { ...b, track_ids: b.track_ids.filter((id) => id !== trackId) }
          ),
        });
      }

      return { previousSession };
    },
    onError: (_err, _vars, context) => {
      // Rollback on error
      if (context?.previousSession) {
        queryClient.setQueryData(queryKey, context.previousSession);
      }
    },
    onSettled: invalidate,
  });

  const unassignTrackMutation = useMutation({
    mutationFn: ({ bucketId, trackId }: { bucketId: string; trackId: number }) =>
      bucketsApi.unassignTrack(bucketId, trackId),
    onSuccess: invalidate,
  });

  const reorderTracksMutation = useMutation({
    mutationFn: ({ bucketId, trackIds }: { bucketId: string; trackIds: number[] }) =>
      bucketsApi.reorderTracks(bucketId, trackIds),
    onSuccess: invalidate,
  });

  // Session mutations
  const applyMutation = useMutation({
    mutationFn: () => bucketsApi.applySession(session!.id),
    onSuccess: invalidate,
  });

  const discardMutation = useMutation({
    mutationFn: () => bucketsApi.discardSession(session!.id),
    onSuccess: () => {
      queryClient.removeQueries({ queryKey });
    },
  });

  // Computed values
  const buckets = session?.buckets ?? [];
  const unassignedTrackIds = session?.unassigned_track_ids ?? [];

  const getBucketByIndex = (index: number): Bucket | undefined => {
    return buckets.find((b) => b.position === index) ?? buckets[index];
  };

  return {
    session,
    isLoading,
    error: error as Error | null,

    createBucket: (name, emojiId) => createBucketMutation.mutateAsync({ name, emojiId }),
    updateBucket: (bucketId, updates) => updateBucketMutation.mutateAsync({ bucketId, updates }),
    deleteBucket: (bucketId) => deleteBucketMutation.mutateAsync(bucketId),
    moveBucket: (bucketId, direction) => moveBucketMutation.mutateAsync({ bucketId, direction }),
    shuffleBucket: (bucketId) => shuffleBucketMutation.mutateAsync(bucketId).then(() => {}),

    assignTrack: (bucketId, trackId) => assignTrackMutation.mutateAsync({ bucketId, trackId }),
    unassignTrack: (bucketId, trackId) => unassignTrackMutation.mutateAsync({ bucketId, trackId }),
    reorderTracks: (bucketId, trackIds) => reorderTracksMutation.mutateAsync({ bucketId, trackIds }),

    applyOrder: () => applyMutation.mutateAsync(),
    discardSession: () => discardMutation.mutateAsync(),

    buckets,
    unassignedTrackIds,
    getBucketByIndex,

    isAssigning: assignTrackMutation.isPending,
    isApplying: applyMutation.isPending,
  };
}
```

## Verification
```bash
# TypeScript check
cd web/frontend && npx tsc --noEmit

# Manual test in a component
# const { session, buckets, createBucket } = usePlaylistOrganizer({ playlistId: 1 });
# console.log(session, buckets);
```
