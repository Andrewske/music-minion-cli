import { useQuery, useMutation, useQueryClient, keepPreviousData } from '@tanstack/react-query';
import type { UseQueryResult, UseMutationResult } from '@tanstack/react-query';
import * as artistsApi from '../api/artists';
import type {
  ArtistStats, ArtistDetail, ParetoResult, FeedSyncState,
  GetArtistsOptions, CreateMatchOverrideBody, MatchOverride,
  UnfollowResult, FollowingsSyncResult,
} from '../api/artists';

// ---------------------------------------------------------------------------
// Query hooks
// ---------------------------------------------------------------------------

export function useArtists(opts: GetArtistsOptions = {}): UseQueryResult<ArtistStats[]> {
  return useQuery({
    queryKey: ['artists', 'list', opts],
    queryFn: () => artistsApi.getArtists(opts),
    staleTime: 5 * 60 * 1000,
    placeholderData: keepPreviousData,
  });
}

export function useArtist(id: number | null): UseQueryResult<ArtistDetail> {
  return useQuery({
    queryKey: ['artists', 'detail', id],
    queryFn: () => artistsApi.getArtist(id as number),
    enabled: id != null,
  });
}

export function usePareto(): UseQueryResult<ParetoResult> {
  return useQuery({
    queryKey: ['artists', 'pareto'],
    queryFn: () => artistsApi.getPareto(),
    staleTime: 5 * 60 * 1000,
  });
}

export function useFeedSyncStatus(): UseQueryResult<FeedSyncState> {
  return useQuery({
    queryKey: ['artists', 'feed-sync-status'],
    queryFn: () => artistsApi.getFeedSyncStatus(),
    refetchInterval: 30_000,
  });
}

// ---------------------------------------------------------------------------
// Mutation hooks
// ---------------------------------------------------------------------------

interface UnfollowContext {
  previousLists: Array<[readonly unknown[], ArtistStats[]]>;
}

export function useUnfollowArtist(): UseMutationResult<UnfollowResult, Error, number, UnfollowContext> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: number) => artistsApi.unfollowArtist(id),
    onMutate: async (id: number): Promise<UnfollowContext> => {
      await queryClient.cancelQueries({ queryKey: ['artists', 'list'] });

      const allListQueries = queryClient.getQueriesData<ArtistStats[]>({
        queryKey: ['artists', 'list'],
      });

      const previousLists: Array<[readonly unknown[], ArtistStats[]]> = allListQueries
        .filter((entry): entry is [readonly unknown[], ArtistStats[]] => entry[1] != null)
        .map(([key, snapshot]) => [key, snapshot]);

      for (const [key] of previousLists) {
        queryClient.setQueryData<ArtistStats[]>(key as Parameters<typeof queryClient.setQueryData>[0], (old) => {
          if (!old) return old;
          return old.map((artist) => {
            if (artist.id !== id) return artist;
            return {
              ...artist,
              is_following: false,
              feed_noise_7d: 0,
              feed_noise_30d: 0,
              last_activity_at: null,
            };
          });
        });
      }

      return { previousLists };
    },
    onError: (_err, _id, context) => {
      if (!context) return;
      for (const [key, data] of context.previousLists) {
        queryClient.setQueryData(key as Parameters<typeof queryClient.setQueryData>[0], data);
      }
    },
    onSettled: (_data, _err, id) => {
      void queryClient.invalidateQueries({ queryKey: ['artists', 'list'] });
      void queryClient.invalidateQueries({ queryKey: ['artists', 'detail', id] });
      void queryClient.invalidateQueries({ queryKey: ['artists', 'pareto'] });
    },
  });
}

export function useFeedSync(): UseMutationResult<FeedSyncState, Error, void, unknown> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => artistsApi.syncFeed(),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['artists', 'list'] });
      void queryClient.invalidateQueries({ queryKey: ['artists', 'feed-sync-status'] });
      void queryClient.invalidateQueries({ queryKey: ['artists', 'pareto'] });
    },
  });
}

export function useFollowingsSync(): UseMutationResult<FollowingsSyncResult, Error, void, unknown> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => artistsApi.syncFollowings(),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['artists', 'list'] });
    },
  });
}

export function useMatchOverride(): UseMutationResult<MatchOverride, Error, CreateMatchOverrideBody, unknown> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: CreateMatchOverrideBody) => artistsApi.createMatchOverride(body),
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({ queryKey: ['artists', 'list'] });
      void queryClient.invalidateQueries({ queryKey: ['artists', 'detail', variables.discovery_artist_id] });
    },
  });
}

export function useDeleteMatchOverride(): UseMutationResult<void, Error, number, unknown> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (overrideId: number) => artistsApi.deleteMatchOverride(overrideId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['artists', 'list'] });
      void queryClient.invalidateQueries({ queryKey: ['artists', 'detail'] });
    },
  });
}
