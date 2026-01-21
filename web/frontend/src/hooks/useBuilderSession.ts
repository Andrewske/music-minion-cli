 import { useState } from 'react';
 import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
 import { builderApi } from '../api/builder';
 import type { Filter } from '../api/builder';

 export type SortField = 'artist' | 'title' | 'year' | 'bpm' | 'elo_rating';
 export type SortDirection = 'asc' | 'desc';

export function useBuilderSession(playlistId: number | null) {
  const queryClient = useQueryClient();

  // Sort state
  const [sortField, setSortField] = useState<SortField>('artist');
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc');

  // Fetch active session (no polling - rely on manual refetch)
  const { data: session, isLoading, error } = useQuery({
    queryKey: ['builder-session', playlistId],
    queryFn: () => playlistId ? builderApi.getSession(playlistId) : null,
    enabled: !!playlistId
  });

  // Start session mutation
  const startSession = useMutation({
    mutationFn: (playlistId: number) => builderApi.startSession(playlistId),
    onSuccess: (data) => {
      queryClient.setQueryData(['builder-session', data.playlist_id], data);
      // Also activate builder mode in backend context
      builderApi.activateBuilderMode(data.playlist_id);
    },
    onError: (error: Error) => {
      console.error('Failed to start session:', error);
    }
  });

  // Add track mutation
  const addTrack = useMutation({
    mutationFn: (trackId: number) => {
      if (!playlistId) throw new Error('No playlist selected');
      return builderApi.addTrack(playlistId, trackId);
    },
    onSuccess: () => {
      // Invalidate related queries
      queryClient.invalidateQueries({ queryKey: ['playlists'] });
      queryClient.invalidateQueries({ queryKey: ['builder-candidates', playlistId] });
    },
    onError: (error: Error) => {
      console.error('Failed to add track:', error);
    }
  });

  // Skip track mutation
  const skipTrack = useMutation({
    mutationFn: (trackId: number) => {
      if (!playlistId) throw new Error('No playlist selected');
      return builderApi.skipTrack(playlistId, trackId);
    },
    onSuccess: () => {
      // Invalidate related queries
      queryClient.invalidateQueries({ queryKey: ['builder-skipped', playlistId] });
      queryClient.invalidateQueries({ queryKey: ['builder-candidates', playlistId] });
    },
    onError: (error: Error) => {
      console.error('Failed to skip track:', error);
    }
  });

  // End session mutation
  const endSession = useMutation({
    mutationFn: () => {
      if (!playlistId) throw new Error('No playlist selected');
      return builderApi.endSession(playlistId);
    },
    onSuccess: () => {
      queryClient.removeQueries({ queryKey: ['builder-session', playlistId] });
      // Deactivate builder mode in backend context
      builderApi.deactivateBuilderMode();
    }
  });

  // Fetch filters
  const { data: filters } = useQuery({
    queryKey: ['builder-filters', playlistId],
    queryFn: () => playlistId ? builderApi.getFilters(playlistId) : [],
    enabled: !!playlistId
  });

  // Update filters mutation
  const updateFilters = useMutation({
    mutationFn: (newFilters: Filter[]) => {
      if (!playlistId) throw new Error('No playlist selected');
      return builderApi.updateFilters(playlistId, newFilters);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['builder-filters', playlistId] });
      queryClient.invalidateQueries({ queryKey: ['builder-session', playlistId] });
      queryClient.invalidateQueries({ queryKey: ['builder-candidates', playlistId] });
    }
  });

  return {
    // Session state
    session,
    isLoading,
    error,

    // Session mutations
    startSession,
    endSession,

    // Track mutations
    addTrack,
    skipTrack,

    // Filter state
    filters,
    updateFilters,

    // Sort state
    sortField,
    sortDirection,
    setSortField,
    setSortDirection,

    // Loading states
    isAddingTrack: addTrack.isPending,
    isSkippingTrack: skipTrack.isPending
  };
}
