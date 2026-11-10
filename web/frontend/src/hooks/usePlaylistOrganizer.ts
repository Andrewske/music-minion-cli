import { useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as bucketsApi from '../api/buckets';
import type {
  BucketSession,
  Bucket,
  LinkBucketResult,
  PullLinkedTracksResponse,
  SessionSummary,
  SyncSoundCloudResponse,
} from '../api/buckets';

/** Cache key for the session currently loaded (status 'active') for a playlist. */
export const organizerSessionKey = (playlistId: number): readonly ['organizer', 'session', number] =>
  ['organizer', 'session', playlistId] as const;

/** Cache key for the list of non-discarded sessions for a playlist. */
export const organizerSessionsKey = (playlistId: number): readonly ['organizer', 'sessions', number] =>
  ['organizer', 'sessions', playlistId] as const;

/**
 * Session list for the switcher. Pass `enabled` from the dropdown's open state
 * so the list is only fetched when the user looks at it.
 */
export function useOrganizerSessions(
  playlistId: number,
  enabled: boolean
): { sessions: SessionSummary[]; isLoading: boolean } {
  const { data, isLoading } = useQuery({
    queryKey: organizerSessionsKey(playlistId),
    queryFn: () => bucketsApi.listSessions(playlistId),
    enabled: enabled && !!playlistId,
    staleTime: 30 * 1000,
  });
  return { sessions: data ?? [], isLoading };
}

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
  /** Returns tracks that could be pulled into the bucket from the linked playlist. */
  linkBucket: (bucketId: string, playlistId: number | null) => Promise<LinkBucketResult>;
  pullLinkedTracks: (bucketId: string) => Promise<PullLinkedTracksResponse>;

  // Track operations
  assignTrack: (bucketId: string, trackId: number) => Promise<void>;
  unassignTrack: (bucketId: string, trackId: number) => Promise<void>;
  reorderTracks: (bucketId: string, trackIds: number[]) => Promise<void>;

  // Session operations
  applyOrder: () => Promise<void>;
  /** Resolves to the fresh session that replaces the finished one. */
  finalizeSession: () => Promise<BucketSession>;
  newSession: (name?: string | null) => Promise<BucketSession>;
  switchSession: (sessionId: string) => Promise<BucketSession>;
  renameSession: (sessionId: string, name: string | null) => Promise<void>;
  /**
   * Discards the session (strips bucket emojis). Deleting the loaded one loads
   * and resolves to a fresh session; deleting any other resolves to null.
   */
  deleteSession: (sessionId: string) => Promise<BucketSession | null>;

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
  isSwitching: boolean;
}

export function usePlaylistOrganizer(
  options: UsePlaylistOrganizerOptions
): UsePlaylistOrganizerReturn {
  const { playlistId, enabled = true } = options;
  const queryClient = useQueryClient();

  const queryKey = organizerSessionKey(playlistId);
  const sessionsQueryKey = organizerSessionsKey(playlistId);

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

  const pullLinkedMutation = useMutation({
    mutationFn: (bucketId: string) => bucketsApi.pullLinkedTracks(bucketId),
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

  // Restore an optimistic snapshot, but only if the same session is still
  // loaded: a failure that lands after a switch must not resurrect the old one.
  const rollback = (previous: BucketSession | undefined): void => {
    if (!previous) return;
    const loaded = queryClient.getQueryData<BucketSession>(queryKey);
    if (loaded && loaded.id !== previous.id) return;
    queryClient.setQueryData(queryKey, previous);
  };

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
      rollback(context?.previousSession);
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
      rollback(context?.previousSession);
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

  // Any refetch of the loaded session that started before a session change
  // would land afterwards with the old (now parked) session. Cancel them.
  const cancelLoadedRefetch = (): Promise<void> => queryClient.cancelQueries({ queryKey });

  // Loading another session: write the returned session straight into the
  // loaded-session cache (no refetch flash), then refresh the list.
  const loadSession = async (loaded: BucketSession): Promise<void> => {
    await cancelLoadedRefetch();
    queryClient.setQueryData<BucketSession>(queryKey, loaded);
    queryClient.invalidateQueries({ queryKey: sessionsQueryKey });
  };

  const finalizeSessionMutation = useMutation({
    mutationFn: async (): Promise<BucketSession> => {
      if (!session) throw new Error('No active session');
      await bucketsApi.finalizeSession(session.id);
      // get-or-create now hands back a fresh active session
      return bucketsApi.createOrResumeSession(playlistId);
    },
    onMutate: cancelLoadedRefetch,
    onSuccess: loadSession,
  });

  const newSessionMutation = useMutation({
    mutationFn: (name: string | null) => bucketsApi.createNewSession(playlistId, name),
    onMutate: cancelLoadedRefetch,
    onSuccess: loadSession,
  });

  const switchSessionMutation = useMutation({
    mutationFn: (sessionId: string) => bucketsApi.activateSession(sessionId),
    onMutate: cancelLoadedRefetch,
    onSuccess: loadSession,
  });

  const renameSessionMutation = useMutation({
    mutationFn: (params: { sessionId: string; name: string | null }) =>
      bucketsApi.renameSession(params.sessionId, params.name),
    onSuccess: (_data, { sessionId, name }) => {
      queryClient.setQueryData<BucketSession>(queryKey, (prev) =>
        prev && prev.id === sessionId ? { ...prev, name } : prev
      );
      queryClient.invalidateQueries({ queryKey: sessionsQueryKey });
    },
  });

  const deleteSessionMutation = useMutation({
    // Resolves to the replacement session when the loaded one was deleted.
    mutationFn: async (sessionId: string): Promise<BucketSession | null> => {
      const wasLoaded = queryClient.getQueryData<BucketSession>(queryKey)?.id === sessionId;
      if (wasLoaded) await cancelLoadedRefetch();
      await bucketsApi.discardSession(sessionId);
      return wasLoaded ? bucketsApi.createOrResumeSession(playlistId) : null;
    },
    onSuccess: async (replacement) => {
      if (replacement) return loadSession(replacement);
      queryClient.invalidateQueries({ queryKey: sessionsQueryKey });
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
    async (bucketId: string, playlistId: number | null): Promise<LinkBucketResult> => {
      return linkBucketMutation.mutateAsync({ bucketId, playlistId });
    },
    [linkBucketMutation]
  );

  const pullLinkedTracks = useCallback(
    async (bucketId: string): Promise<PullLinkedTracksResponse> => {
      return pullLinkedMutation.mutateAsync(bucketId);
    },
    [pullLinkedMutation]
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
    async (): Promise<BucketSession> => {
      return finalizeSessionMutation.mutateAsync();
    },
    [finalizeSessionMutation]
  );

  const newSession = useCallback(
    async (name: string | null = null): Promise<BucketSession> => {
      return newSessionMutation.mutateAsync(name);
    },
    [newSessionMutation]
  );

  const switchSession = useCallback(
    async (sessionId: string): Promise<BucketSession> => {
      return switchSessionMutation.mutateAsync(sessionId);
    },
    [switchSessionMutation]
  );

  const renameSession = useCallback(
    async (sessionId: string, name: string | null): Promise<void> => {
      await renameSessionMutation.mutateAsync({ sessionId, name });
    },
    [renameSessionMutation]
  );

  const deleteSession = useCallback(
    async (sessionId: string): Promise<BucketSession | null> => {
      return deleteSessionMutation.mutateAsync(sessionId);
    },
    [deleteSessionMutation]
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
    pullLinkedTracks,

    // Track operations
    assignTrack,
    unassignTrack,
    reorderTracks,

    // Session operations
    applyOrder,
    finalizeSession,
    newSession,
    switchSession,
    renameSession,
    deleteSession,

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
    isSwitching: newSessionMutation.isPending || switchSessionMutation.isPending,
  };
}
