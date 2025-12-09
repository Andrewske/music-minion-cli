import { useMutation, useQueryClient } from '@tanstack/react-query';
import { startSession, recordComparison } from '../api/comparisons';
import { archiveTrack } from '../api/tracks';
import { useComparisonStore } from '../stores/comparisonStore';
import type { StartSessionRequest, RecordComparisonRequest } from '../types';

export function useStartSession() {
  const queryClient = useQueryClient();
  const { setSession } = useComparisonStore();

  return useMutation({
    mutationFn: (request: StartSessionRequest) => startSession(request),
    onSuccess: (response) => {
      setSession(response.session_id, response.pair);
      // Invalidate any cached comparison data
      queryClient.invalidateQueries({ queryKey: ['comparisons'] });
    },
  });
}

export function useRecordComparison() {
  const { incrementCompleted, setCurrentPair, setPlaying } = useComparisonStore();

  return useMutation({
    mutationFn: (request: RecordComparisonRequest) => recordComparison(request),
    onSuccess: (response) => {
      if (response.success) {
        incrementCompleted();

        // Clear playback state when loading new pair
        setPlaying(null);

        // If there's a next pair, update the store
        if (response.next_pair) {
          setCurrentPair(response.next_pair);
        }
      }
    },
  });
}

export function useArchiveTrack() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (trackId: number) => archiveTrack(trackId),
    onSuccess: () => {
      // Invalidate comparison queries to refresh available tracks
      queryClient.invalidateQueries({ queryKey: ['comparisons'] });
    },
  });
}