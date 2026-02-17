import { useState } from 'react';
import { useInfiniteQuery, useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import type { SortingState } from '@tanstack/react-table';
import type { UseMutationResult } from '@tanstack/react-query';
import { builderApi } from '../api/builder';
import type { Filter, Track, TrackActionResponse } from '../api/builder';
import {
  getSmartPlaylistTracks,
  getSmartFilters,
  updateSmartFilters,
  skipSmartPlaylistTrack,
  unskipSmartPlaylistTrack,
  getSmartPlaylistSkippedTracks,
} from '../api/playlists';

const PAGE_SIZE = 100;

export interface UsePlaylistBuilderReturn {
  // Tracks
  tracks: Track[];
  fetchNextPage: () => void;
  hasNextPage: boolean;
  isFetchingNextPage: boolean;

  // Sorting (hook owns state)
  sorting: SortingState;
  setSorting: (sorting: SortingState) => void;

  // Mutations
  addTrack: UseMutationResult<TrackActionResponse, Error, number, unknown>;
  skipTrack: UseMutationResult<void, Error, number, unknown>;
  unskipTrack: UseMutationResult<void, Error, number, unknown>;

  // Skipped tracks
  skippedTracks: Track[];

  // Filters (smart playlists only, empty for manual)
  filters: Filter[];
  updateFilters: UseMutationResult<Filter[], Error, Filter[], unknown>;

  // Loading states
  isLoading: boolean;
  isAddingTrack: boolean;
  isSkippingTrack: boolean;
}

export function usePlaylistBuilder(
  playlistId: number,
  playlistType: 'manual' | 'smart'
): UsePlaylistBuilderReturn {
  const queryClient = useQueryClient();

  // Sorting state - owned by hook
  const [sorting, setSorting] = useState<SortingState>([
    { id: 'artist', desc: false },
  ]);
  const sortField = sorting[0]?.id ?? 'artist';
  const sortDirection = sorting[0]?.desc ? 'desc' : 'asc';

  // Unified infinite query for tracks
  const {
    data,
    fetchNextPage,
    hasNextPage = false,
    isFetchingNextPage,
    isLoading: isTracksLoading,
  } = useInfiniteQuery({
    queryKey: ['builder-tracks', playlistId, playlistType, sortField, sortDirection],
    queryFn: async ({ pageParam = 0 }) => {
      if (playlistType === 'manual') {
        return builderApi.getCandidates(playlistId, PAGE_SIZE, pageParam, sortField, sortDirection);
      } else {
        const result = await getSmartPlaylistTracks(playlistId, PAGE_SIZE, pageParam, sortField, sortDirection);
        // Normalize response to match candidates shape
        return {
          candidates: result.tracks,
          total: result.total,
          hasMore: result.hasMore,
        };
      }
    },
    initialPageParam: 0,
    getNextPageParam: (lastPage, allPages) =>
      lastPage.hasMore ? allPages.length * PAGE_SIZE : undefined,
    enabled: !!playlistId,
  });

  // Flatten tracks from all pages
  const tracks = data?.pages.flatMap((p) => p.candidates) ?? [];

  // Skipped tracks query
  const { data: skippedTracks = [] } = useQuery({
    queryKey: ['builder-skipped', playlistId, playlistType],
    queryFn: () =>
      playlistType === 'manual'
        ? builderApi.getSkippedTracks(playlistId)
        : getSmartPlaylistSkippedTracks(playlistId),
    enabled: !!playlistId,
  });

  // Filters query (smart playlists only)
  const { data: filters = [] } = useQuery({
    queryKey: ['builder-filters', playlistId],
    queryFn: () =>
      playlistType === 'smart'
        ? getSmartFilters(playlistId)
        : Promise.resolve([]),
    enabled: !!playlistId,
  });

  // Add track mutation (manual playlists only)
  const addTrack = useMutation({
    mutationFn: (trackId: number) => {
      if (playlistType !== 'manual') {
        throw new Error('Cannot add tracks to smart playlists');
      }
      return builderApi.addTrack(playlistId, trackId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['builder-tracks', playlistId] });
      queryClient.invalidateQueries({ queryKey: ['playlists'] });
    },
  });

  // Skip track mutation (unified, permanent for both types)
  const skipTrack = useMutation({
    mutationFn: async (trackId: number): Promise<void> => {
      if (playlistType === 'manual') {
        await builderApi.skipTrack(playlistId, trackId);
      } else {
        await skipSmartPlaylistTrack(playlistId, trackId);
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['builder-tracks', playlistId] });
      queryClient.invalidateQueries({ queryKey: ['builder-skipped', playlistId] });
    },
  });

  // Unskip track mutation (unified for both types)
  const unskipTrack = useMutation({
    mutationFn: async (trackId: number): Promise<void> => {
      if (playlistType === 'manual') {
        await builderApi.unskipTrack(playlistId, trackId);
      } else {
        await unskipSmartPlaylistTrack(playlistId, trackId);
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['builder-tracks', playlistId] });
      queryClient.invalidateQueries({ queryKey: ['builder-skipped', playlistId] });
    },
  });

  // Update filters mutation (smart playlists only)
  const updateFiltersMutation = useMutation({
    mutationFn: (newFilters: Filter[]) => {
      if (playlistType !== 'smart') {
        throw new Error('Filters only apply to smart playlists');
      }
      return updateSmartFilters(playlistId, newFilters);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['builder-filters', playlistId] });
      queryClient.invalidateQueries({ queryKey: ['builder-tracks', playlistId] });
    },
  });

  return {
    // Tracks
    tracks,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,

    // Sorting
    sorting,
    setSorting,

    // Mutations
    addTrack,
    skipTrack,
    unskipTrack,

    // Skipped tracks
    skippedTracks,

    // Filters
    filters,
    updateFilters: updateFiltersMutation,

    // Loading states
    isLoading: isTracksLoading,
    isAddingTrack: addTrack.isPending,
    isSkippingTrack: skipTrack.isPending,
  };
}
