/**
 * Playlist organizer hook — manages bucket sessions.
 * Port of web/frontend/src/hooks/usePlaylistOrganizer.ts.
 * Uses shared bucket API + React Query with optimistic updates.
 */
import { useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as bucketsApi from '@music-minion/shared';
import type { Bucket, BucketSession } from '@music-minion/shared';
import { organizerSessionKey } from './useOrganizerSessions';

interface UsePlaylistOrganizerOptions {
  playlistId: number;
  enabled?: boolean;
}

export interface UsePlaylistOrganizerReturn {
  session: BucketSession | undefined;
  isLoading: boolean;
  error: Error | null;
  buckets: Bucket[];
  unassignedTrackIds: number[];
  createBucket: (name: string, emojiId?: string) => Promise<Bucket>;
  updateBucket: (bucketId: string, updates: { name?: string; emoji_id?: string | null }) => Promise<Bucket>;
  deleteBucket: (bucketId: string) => Promise<void>;
  moveBucket: (bucketId: string, direction: 'up' | 'down') => Promise<void>;
  shuffleBucket: (bucketId: string) => Promise<number[]>;
  assignTrack: (bucketId: string, trackId: number) => Promise<void>;
  unassignTrack: (bucketId: string, trackId: number) => Promise<void>;
  reorderTracks: (bucketId: string, trackIds: number[]) => Promise<void>;
  applyOrder: () => Promise<void>;
  isApplying: boolean;
}

export function usePlaylistOrganizer({ playlistId, enabled = true }: UsePlaylistOrganizerOptions): UsePlaylistOrganizerReturn {
  const queryClient = useQueryClient();
  const queryKey = organizerSessionKey(playlistId);

  // Restore an optimistic snapshot only if the same session is still loaded:
  // a failure that lands after a session switch must not resurrect the old one.
  const rollback = (prev: BucketSession | undefined): void => {
    if (!prev) return;
    const loaded = queryClient.getQueryData<BucketSession>(queryKey);
    if (loaded && loaded.id !== prev.id) return;
    queryClient.setQueryData(queryKey, prev);
  };

  const { data: session, isLoading, error } = useQuery({
    queryKey,
    queryFn: () => bucketsApi.createOrResumeSession(playlistId),
    enabled: enabled && !!playlistId,
    staleTime: 5 * 60 * 1000,
  });

  // === Bucket mutations ===

  const createBucketMutation = useMutation({
    mutationFn: (params: { name: string; emojiId?: string }) => {
      if (!session) throw new Error('No active session');
      return bucketsApi.createBucket(session.id, { name: params.name, emoji_id: params.emojiId });
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey }),
  });

  const updateBucketMutation = useMutation({
    mutationFn: (params: { bucketId: string; updates: { name?: string; emoji_id?: string | null } }) =>
      bucketsApi.updateBucket(params.bucketId, params.updates),
    onSuccess: () => queryClient.invalidateQueries({ queryKey }),
  });

  const deleteBucketMutation = useMutation({
    mutationFn: (bucketId: string) => bucketsApi.deleteBucket(bucketId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey }),
  });

  const moveBucketMutation = useMutation({
    mutationFn: (params: { bucketId: string; direction: 'up' | 'down' }) =>
      bucketsApi.moveBucket(params.bucketId, params.direction),
    onSuccess: () => queryClient.invalidateQueries({ queryKey }),
  });

  const shuffleBucketMutation = useMutation({
    mutationFn: (bucketId: string) => bucketsApi.shuffleBucket(bucketId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey }),
  });

  // === Track mutations with optimistic updates ===

  const assignTrackMutation = useMutation({
    mutationFn: (params: { bucketId: string; trackId: number }) =>
      bucketsApi.assignTrack(params.bucketId, params.trackId),
    onMutate: async ({ bucketId, trackId }) => {
      await queryClient.cancelQueries({ queryKey });
      const prev = queryClient.getQueryData<BucketSession>(queryKey);
      if (prev) {
        queryClient.setQueryData<BucketSession>(queryKey, {
          ...prev,
          buckets: prev.buckets.map((b) =>
            b.id === bucketId && !b.track_ids.includes(trackId)
              ? { ...b, track_ids: [...b.track_ids, trackId] }
              : b
          ),
          unassigned_track_ids: prev.unassigned_track_ids.filter((id) => id !== trackId),
        });
      }
      return { prev };
    },
    onError: (_err, _params, context) => rollback(context?.prev),
    onSettled: () => queryClient.invalidateQueries({ queryKey }),
  });

  const unassignTrackMutation = useMutation({
    mutationFn: (params: { bucketId: string; trackId: number }) =>
      bucketsApi.unassignTrack(params.bucketId, params.trackId),
    onMutate: async ({ bucketId, trackId }) => {
      await queryClient.cancelQueries({ queryKey });
      const prev = queryClient.getQueryData<BucketSession>(queryKey);
      if (prev) {
        const updatedBuckets = prev.buckets.map((b) =>
          b.id === bucketId
            ? { ...b, track_ids: b.track_ids.filter((id) => id !== trackId) }
            : b
        );
        const stillAssigned = updatedBuckets.some((b) => b.track_ids.includes(trackId));
        queryClient.setQueryData<BucketSession>(queryKey, {
          ...prev,
          buckets: updatedBuckets,
          unassigned_track_ids: stillAssigned
            ? prev.unassigned_track_ids
            : [...prev.unassigned_track_ids, trackId],
        });
      }
      return { prev };
    },
    onError: (_err, _params, context) => rollback(context?.prev),
    onSettled: () => queryClient.invalidateQueries({ queryKey }),
  });

  const reorderTracksMutation = useMutation({
    mutationFn: (params: { bucketId: string; trackIds: number[] }) =>
      bucketsApi.reorderTracks(params.bucketId, params.trackIds),
    onSuccess: () => queryClient.invalidateQueries({ queryKey }),
  });

  // === Session mutations ===

  const applyMutation = useMutation({
    mutationFn: () => {
      if (!session) throw new Error('No active session');
      return bucketsApi.applySession(session.id);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey });
      queryClient.invalidateQueries({ queryKey: ['playlists'] });
    },
  });

  // === Wrapper functions ===

  return {
    session,
    isLoading,
    error: error ?? null,
    buckets: session?.buckets ?? [],
    unassignedTrackIds: session?.unassigned_track_ids ?? [],

    createBucket: useCallback(
      (name: string, emojiId?: string) => createBucketMutation.mutateAsync({ name, emojiId }),
      [createBucketMutation]
    ),
    updateBucket: useCallback(
      (bucketId: string, updates: { name?: string; emoji_id?: string | null }) =>
        updateBucketMutation.mutateAsync({ bucketId, updates }),
      [updateBucketMutation]
    ),
    deleteBucket: useCallback(
      (bucketId: string) => deleteBucketMutation.mutateAsync(bucketId),
      [deleteBucketMutation]
    ),
    moveBucket: useCallback(
      (bucketId: string, direction: 'up' | 'down') => moveBucketMutation.mutateAsync({ bucketId, direction }),
      [moveBucketMutation]
    ),
    shuffleBucket: useCallback(
      (bucketId: string) => shuffleBucketMutation.mutateAsync(bucketId),
      [shuffleBucketMutation]
    ),
    assignTrack: useCallback(
      (bucketId: string, trackId: number) => assignTrackMutation.mutateAsync({ bucketId, trackId }),
      [assignTrackMutation]
    ),
    unassignTrack: useCallback(
      (bucketId: string, trackId: number) => unassignTrackMutation.mutateAsync({ bucketId, trackId }),
      [unassignTrackMutation]
    ),
    reorderTracks: useCallback(
      (bucketId: string, trackIds: number[]) => reorderTracksMutation.mutateAsync({ bucketId, trackIds }),
      [reorderTracksMutation]
    ),
    applyOrder: useCallback(() => applyMutation.mutateAsync(), [applyMutation]),

    isApplying: applyMutation.isPending,
  };
}
