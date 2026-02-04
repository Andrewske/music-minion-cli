import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import type { SortingState } from '@tanstack/react-table';
import { getSmartFilters, updateSmartFilters } from '../api/playlists';
import type { Filter, Track } from '../api/builder';

export function useSmartPlaylistEditor(playlistId: number) {
  const queryClient = useQueryClient();

  // Sorting state - mirrors manual builder pattern
  const [sorting, setSorting] = useState<SortingState>([
    { id: 'artist', desc: false }
  ]);
  const sortField = sorting[0]?.id ?? 'artist';
  const sortDirection = sorting[0]?.desc ? 'desc' : 'asc';

  // Fetch filters for the smart playlist
  const filtersQuery = useQuery({
    queryKey: ['smart-playlist-filters', playlistId],
    queryFn: () => getSmartFilters(playlistId),
    enabled: !!playlistId,
  });

  // Fetch tracks matching the filters with server-side sorting
  const tracksQuery = useQuery({
    queryKey: ['playlist-tracks', playlistId, sortField, sortDirection],
    queryFn: async () => {
      const response = await fetch(
        `/api/playlists/${playlistId}/tracks?sort_field=${sortField}&sort_direction=${sortDirection}`
      );
      if (!response.ok) throw new Error('Failed to fetch tracks');
      const data = await response.json();
      return data.tracks as Track[];
    },
    enabled: !!playlistId,
  });

  // Mutation to update filters
  const updateFiltersMutation = useMutation({
    mutationFn: (filters: Filter[]) => updateSmartFilters(playlistId, filters),
    onSuccess: () => {
      // Invalidate both filters and tracks (tracks depend on filters)
      queryClient.invalidateQueries({ queryKey: ['smart-playlist-filters', playlistId] });
      queryClient.invalidateQueries({ queryKey: ['playlist-tracks', playlistId] });
    },
  });

  return {
    filters: filtersQuery.data ?? [],
    tracks: tracksQuery.data ?? [],
    isLoading: filtersQuery.isLoading || tracksQuery.isLoading,
    isUpdatingFilters: updateFiltersMutation.isPending,
    updateFilters: updateFiltersMutation,
    refetchTracks: tracksQuery.refetch,
    sorting,
    setSorting,
  };
}
