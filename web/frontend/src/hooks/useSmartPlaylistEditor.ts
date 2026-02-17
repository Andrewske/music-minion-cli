import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import type { SortingState } from '@tanstack/react-table';
import { getSmartFilters, updateSmartFilters, skipSmartPlaylistTrack, unskipSmartPlaylistTrack, getSmartPlaylistSkippedTracks } from '../api/playlists';
import type { Filter, Track } from '../api/builder';

export function useSmartPlaylistEditor(playlistId: number) {
  const queryClient = useQueryClient();

  // Sorting state - mirrors manual builder pattern
  const [sorting, setSorting] = useState<SortingState>([
    { id: 'artist', desc: false }
  ]);
  const sortField = sorting[0]?.id ?? 'artist';
  const sortDirection = sorting[0]?.desc ? 'desc' : 'asc';

  // Review mode state
  const [isReviewMode, setIsReviewMode] = useState<boolean>(false);
  const [currentTrackId, setCurrentTrackId] = useState<number | null>(null);

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

  // Fetch skipped tracks
  const skippedTracksQuery = useQuery({
    queryKey: ['smart-playlist-skipped', playlistId],
    queryFn: () => getSmartPlaylistSkippedTracks(playlistId),
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

  // Mutation to skip a track
  const skipTrackMutation = useMutation({
    mutationFn: (trackId: number) => skipSmartPlaylistTrack(playlistId, trackId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['playlist-tracks', playlistId] });
      queryClient.invalidateQueries({ queryKey: ['smart-playlist-skipped', playlistId] });
    },
  });

  // Mutation to unskip a track
  const unskipTrackMutation = useMutation({
    mutationFn: (trackId: number) => unskipSmartPlaylistTrack(playlistId, trackId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['playlist-tracks', playlistId] });
      queryClient.invalidateQueries({ queryKey: ['smart-playlist-skipped', playlistId] });
    },
  });

  // Derived state for review mode
  const tracks = tracksQuery.data ?? [];
  const currentTrackIndex = tracks.findIndex(t => t.id === currentTrackId);
  const currentTrack = currentTrackId !== null ? tracks.find(t => t.id === currentTrackId) ?? null : null;

  // Navigation functions
  const nextTrack = (): void => {
    if (tracks.length === 0) return;

    const nextIndex = currentTrackIndex + 1;
    if (nextIndex >= tracks.length) {
      // All tracks reviewed - exit review mode
      setIsReviewMode(false);
      setCurrentTrackId(null);
    } else {
      setCurrentTrackId(tracks[nextIndex].id);
    }
  };

  const previousTrack = (): void => {
    if (tracks.length === 0) return;

    if (currentTrackIndex === 0) {
      // Wrap to last track
      setCurrentTrackId(tracks[tracks.length - 1].id);
    } else {
      const prevIndex = currentTrackIndex - 1;
      setCurrentTrackId(tracks[prevIndex].id);
    }
  };

  return {
    filters: filtersQuery.data ?? [],
    tracks,
    isLoading: filtersQuery.isLoading || tracksQuery.isLoading,
    isUpdatingFilters: updateFiltersMutation.isPending,
    updateFilters: updateFiltersMutation,
    refetchTracks: tracksQuery.refetch,
    sorting,
    setSorting,
    skipTrack: skipTrackMutation,
    unskipTrack: unskipTrackMutation,
    skippedTracks: skippedTracksQuery.data ?? [],
    currentTrack,
    currentTrackIndex,
    nextTrack,
    previousTrack,
    isReviewMode,
    setIsReviewMode,
  };
}
