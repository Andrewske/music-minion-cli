import { useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as bucketsApi from '../api/buckets';
import type { BucketSession, Bucket, SyncSoundCloudResponse } from '../api/buckets';

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
  linkBucket: (bucketId: string, playlistId: number | null) => Promise<void>;

  // Track operations
  assignTrack: (bucketId: string, trackId: number) => Promise<void>;
  unassignTrack: (bucketId: string, trackId: number) => Promise<void>;
  reorderTracks: (bucketId: string, trackIds: number[]) => Promise<void>;

  // Session operations
  applyOrder: () => Promise<void>;
  finalizeSession: () => Promise<void>;
  discardSession: () => Promise<void>;

  // Computed
  buckets: Bucket[];
  unassignedTrackIds: number[];
  getBucketByIndex: (index: number) => Bucket | undefined;

  // SoundCloud sync
  syncBucketSoundCloud: (bucketId: string) => Promise<SyncSoundCloudResponse>;
  syncingBucketId: string | null;

  // Loading states (for UI feedback)
  isAssigning: boolean;
  isApplying: boolean;
  isFinalizing: boolean;
  isLinking: boolean;
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

  const linkBucketMutation = useMutation({
    mutationFn: (params: { bucketId: string; playlistId: number | null }) => {
      return bucketsApi.linkBucket(params.bucketId, params.playlistId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey });
      queryClient.invalidateQueries({ queryKey: ['playlists'] });
    },
  });

  const syncSoundCloudMutation = useMutation({
    mutationFn: (bucketId: string) => bucketsApi.syncBucketSoundCloud(bucketId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey });
      queryClient.invalidateQueries({ queryKey: ['playlists'] });
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
        // Optimistically update: remove track from unassigned, add to target bucket (keep in other buckets)
        const updatedBuckets = previousSession.buckets.map((bucket) => {
          if (bucket.id === bucketId && !bucket.track_ids.includes(trackId)) {
            return { ...bucket, track_ids: [...bucket.track_ids, trackId] };
          }
          return bucket; // Keep all other buckets unchanged
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
    onError: (err, params, context) => {
      // Log error for debugging
      console.error('Failed to assign track:', err, params);
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
        // Remove track from bucket
        const updatedBuckets = previousSession.buckets.map((bucket) => {
          if (bucket.id === bucketId) {
            return { ...bucket, track_ids: bucket.track_ids.filter((id) => id !== trackId) };
          }
          return bucket;
        });

        // Only add to unassigned if track is not in ANY other bucket
        const stillInOtherBucket = updatedBuckets.some(
          (b) => b.id !== bucketId && b.track_ids.includes(trackId)
        );
        const updatedUnassigned = stillInOtherBucket
          ? previousSession.unassigned_track_ids
          : previousSession.unassigned_track_ids.includes(trackId)
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

  const finalizeSessionMutation = useMutation({
    mutationFn: () => {
      if (!session) throw new Error('No active session');
      return bucketsApi.finalizeSession(session.id);
    },
    onSuccess: () => {
      queryClient.removeQueries({ queryKey });
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
  const createBucket = useCallback(
    async (name: string, emojiId?: string): Promise<Bucket> => {
      return createBucketMutation.mutateAsync({ name, emojiId });
    },
    [createBucketMutation]
  );

  const updateBucket = useCallback(
    async (
      bucketId: string,
      updates: { name?: string; emoji_id?: string | null }
    ): Promise<void> => {
      await updateBucketMutation.mutateAsync({ bucketId, updates });
    },
    [updateBucketMutation]
  );

  const deleteBucket = useCallback(
    async (bucketId: string): Promise<void> => {
      await deleteBucketMutation.mutateAsync(bucketId);
    },
    [deleteBucketMutation]
  );

  const moveBucket = useCallback(
    async (bucketId: string, direction: 'up' | 'down'): Promise<void> => {
      await moveBucketMutation.mutateAsync({ bucketId, direction });
    },
    [moveBucketMutation]
  );

  const shuffleBucket = useCallback(
    async (bucketId: string): Promise<void> => {
      await shuffleBucketMutation.mutateAsync(bucketId);
    },
    [shuffleBucketMutation]
  );

  const linkBucket = useCallback(
    async (bucketId: string, playlistId: number | null): Promise<void> => {
      await linkBucketMutation.mutateAsync({ bucketId, playlistId });
    },
    [linkBucketMutation]
  );

  const syncBucketSoundCloud = useCallback(
    async (bucketId: string): Promise<SyncSoundCloudResponse> => {
      return syncSoundCloudMutation.mutateAsync(bucketId);
    },
    [syncSoundCloudMutation]
  );

  const syncingBucketId = syncSoundCloudMutation.isPending ? (syncSoundCloudMutation.variables ?? null) : null;

  const assignTrack = useCallback(
    async (bucketId: string, trackId: number): Promise<void> => {
      await assignTrackMutation.mutateAsync({ bucketId, trackId });
    },
    [assignTrackMutation]
  );

  const unassignTrack = useCallback(
    async (bucketId: string, trackId: number): Promise<void> => {
      await unassignTrackMutation.mutateAsync({ bucketId, trackId });
    },
    [unassignTrackMutation]
  );

  const reorderTracks = useCallback(
    async (bucketId: string, trackIds: number[]): Promise<void> => {
      await reorderTracksMutation.mutateAsync({ bucketId, trackIds });
    },
    [reorderTracksMutation]
  );

  const applyOrder = useCallback(
    async (): Promise<void> => {
      await applyOrderMutation.mutateAsync();
    },
    [applyOrderMutation]
  );

  const finalizeSession = useCallback(
    async (): Promise<void> => {
      await finalizeSessionMutation.mutateAsync();
    },
    [finalizeSessionMutation]
  );

  const discardSession = useCallback(
    async (): Promise<void> => {
      await discardSessionMutation.mutateAsync();
    },
    [discardSessionMutation]
  );

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
    linkBucket,

    // Track operations
    assignTrack,
    unassignTrack,
    reorderTracks,

    // Session operations
    applyOrder,
    finalizeSession,
    discardSession,

    // SoundCloud sync
    syncBucketSoundCloud,
    syncingBucketId,

    // Computed
    buckets,
    unassignedTrackIds,
    getBucketByIndex,

    // Loading states
    isAssigning: assignTrackMutation.isPending,
    isApplying: applyOrderMutation.isPending,
    isFinalizing: finalizeSessionMutation.isPending,
    isLinking: linkBucketMutation.isPending,
  };
}
