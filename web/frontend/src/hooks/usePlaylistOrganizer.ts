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

export function usePlaylistOrganizer(
  options: UsePlaylistOrganizerOptions
): UsePlaylistOrganizerReturn {
  const { playlistId, enabled = true } = options;
  const queryClient = useQueryClient();

  const queryKey = ['organizer', 'session', playlistId] as const;

  // Main query - creates or resumes session
  const {
    data: session,
    isLoading,
    error,
  } = useQuery({
    queryKey,
    queryFn: () => bucketsApi.createOrResumeSession(playlistId),
    enabled: enabled && !!playlistId,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });

  // Bucket operations

  const createBucketMutation = useMutation({
    mutationFn: (params: { name: string; emojiId?: string }) => {
      if (!session) throw new Error('No active session');
      return bucketsApi.createBucket(session.id, {
        name: params.name,
        emoji_id: params.emojiId,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey });
    },
  });

  const updateBucketMutation = useMutation({
    mutationFn: (params: { bucketId: string; updates: { name?: string; emoji_id?: string | null } }) => {
      return bucketsApi.updateBucket(params.bucketId, params.updates);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey });
    },
  });

  const deleteBucketMutation = useMutation({
    mutationFn: (bucketId: string) => bucketsApi.deleteBucket(bucketId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey });
    },
  });

  const moveBucketMutation = useMutation({
    mutationFn: (params: { bucketId: string; direction: 'up' | 'down' }) => {
      return bucketsApi.moveBucket(params.bucketId, params.direction);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey });
    },
  });

  const shuffleBucketMutation = useMutation({
    mutationFn: (bucketId: string) => bucketsApi.shuffleBucket(bucketId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey });
    },
  });

  // Track operations with optimistic updates

  const assignTrackMutation = useMutation({
    mutationFn: (params: { bucketId: string; trackId: number }) => {
      return bucketsApi.assignTrack(params.bucketId, params.trackId);
    },
    onMutate: async (params) => {
      const { bucketId, trackId } = params;

      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey });

      // Snapshot previous value
      const previousSession = queryClient.getQueryData<BucketSession>(queryKey);

      if (previousSession) {
        // Optimistically update: remove track from unassigned, add to target bucket, remove from other buckets
        const updatedBuckets = previousSession.buckets.map((bucket) => {
          if (bucket.id === bucketId) {
            // Add track to target bucket if not already present
            if (!bucket.track_ids.includes(trackId)) {
              return { ...bucket, track_ids: [...bucket.track_ids, trackId] };
            }
            return bucket;
          }
          // Remove track from other buckets
          return { ...bucket, track_ids: bucket.track_ids.filter((id) => id !== trackId) };
        });

        // Remove from unassigned
        const updatedUnassigned = previousSession.unassigned_track_ids.filter((id) => id !== trackId);

        queryClient.setQueryData<BucketSession>(queryKey, {
          ...previousSession,
          buckets: updatedBuckets,
          unassigned_track_ids: updatedUnassigned,
        });
      }

      return { previousSession };
    },
    onError: (_err, _params, context) => {
      // Rollback on error
      if (context?.previousSession) {
        queryClient.setQueryData(queryKey, context.previousSession);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey });
    },
  });

  const unassignTrackMutation = useMutation({
    mutationFn: (params: { bucketId: string; trackId: number }) => {
      return bucketsApi.unassignTrack(params.bucketId, params.trackId);
    },
    onMutate: async (params) => {
      const { bucketId, trackId } = params;

      await queryClient.cancelQueries({ queryKey });

      const previousSession = queryClient.getQueryData<BucketSession>(queryKey);

      if (previousSession) {
        // Remove track from bucket and add to unassigned
        const updatedBuckets = previousSession.buckets.map((bucket) => {
          if (bucket.id === bucketId) {
            return { ...bucket, track_ids: bucket.track_ids.filter((id) => id !== trackId) };
          }
          return bucket;
        });

        // Add to unassigned if not already present
        const updatedUnassigned = previousSession.unassigned_track_ids.includes(trackId)
          ? previousSession.unassigned_track_ids
          : [...previousSession.unassigned_track_ids, trackId];

        queryClient.setQueryData<BucketSession>(queryKey, {
          ...previousSession,
          buckets: updatedBuckets,
          unassigned_track_ids: updatedUnassigned,
        });
      }

      return { previousSession };
    },
    onError: (_err, _params, context) => {
      if (context?.previousSession) {
        queryClient.setQueryData(queryKey, context.previousSession);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey });
    },
  });

  const reorderTracksMutation = useMutation({
    mutationFn: (params: { bucketId: string; trackIds: number[] }) => {
      return bucketsApi.reorderTracks(params.bucketId, params.trackIds);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey });
    },
  });

  // Session operations

  const applyOrderMutation = useMutation({
    mutationFn: () => {
      if (!session) throw new Error('No active session');
      return bucketsApi.applySession(session.id);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey });
      // Also invalidate playlists since order was applied
      queryClient.invalidateQueries({ queryKey: ['playlists'] });
    },
  });

  const discardSessionMutation = useMutation({
    mutationFn: () => {
      if (!session) throw new Error('No active session');
      return bucketsApi.discardSession(session.id);
    },
    onSuccess: () => {
      queryClient.removeQueries({ queryKey });
    },
  });

  // Computed values
  const buckets: Bucket[] = session?.buckets ?? [];
  const unassignedTrackIds: number[] = session?.unassigned_track_ids ?? [];

  const getBucketByIndex = (index: number): Bucket | undefined => {
    // Find bucket by position or array index
    const byPosition = buckets.find((b) => b.position === index);
    if (byPosition) return byPosition;
    // Fall back to array index (0-based)
    return buckets[index];
  };

  // Wrapper functions for cleaner API
  const createBucket = async (name: string, emojiId?: string): Promise<Bucket> => {
    return createBucketMutation.mutateAsync({ name, emojiId });
  };

  const updateBucket = async (
    bucketId: string,
    updates: { name?: string; emoji_id?: string | null }
  ): Promise<void> => {
    await updateBucketMutation.mutateAsync({ bucketId, updates });
  };

  const deleteBucket = async (bucketId: string): Promise<void> => {
    await deleteBucketMutation.mutateAsync(bucketId);
  };

  const moveBucket = async (bucketId: string, direction: 'up' | 'down'): Promise<void> => {
    await moveBucketMutation.mutateAsync({ bucketId, direction });
  };

  const shuffleBucket = async (bucketId: string): Promise<void> => {
    await shuffleBucketMutation.mutateAsync(bucketId);
  };

  const assignTrack = async (bucketId: string, trackId: number): Promise<void> => {
    await assignTrackMutation.mutateAsync({ bucketId, trackId });
  };

  const unassignTrack = async (bucketId: string, trackId: number): Promise<void> => {
    await unassignTrackMutation.mutateAsync({ bucketId, trackId });
  };

  const reorderTracks = async (bucketId: string, trackIds: number[]): Promise<void> => {
    await reorderTracksMutation.mutateAsync({ bucketId, trackIds });
  };

  const applyOrder = async (): Promise<void> => {
    await applyOrderMutation.mutateAsync();
  };

  const discardSession = async (): Promise<void> => {
    await discardSessionMutation.mutateAsync();
  };

  return {
    // Session data
    session,
    isLoading,
    error: error ?? null,

    // Bucket operations
    createBucket,
    updateBucket,
    deleteBucket,
    moveBucket,
    shuffleBucket,

    // Track operations
    assignTrack,
    unassignTrack,
    reorderTracks,

    // Session operations
    applyOrder,
    discardSession,

    // Computed
    buckets,
    unassignedTrackIds,
    getBucketByIndex,

    // Loading states
    isAssigning: assignTrackMutation.isPending,
    isApplying: applyOrderMutation.isPending,
  };
}
