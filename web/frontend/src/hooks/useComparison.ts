import { useMutation, useQueryClient } from '@tanstack/react-query';
import { startComparison, recordComparison } from '../api/comparisons';
import { archiveTrack, prefetchWaveform } from '../api/tracks';
import { useComparisonStore } from '../stores/comparisonStore';
import type { RecordComparisonRequest } from '../types';

export function useStartComparison() {
  const queryClient = useQueryClient();
  const { startComparison: setComparisonState } = useComparisonStore();

  return useMutation({
    mutationFn: (playlistId: number) => startComparison(playlistId),
    onSuccess: (response, playlistId) => {
      setComparisonState(playlistId, response.pair, response.progress);

      // Prefetch waveforms for current pair
      if (response.pair) {
        prefetchWaveform(response.pair.track_a.id);
        prefetchWaveform(response.pair.track_b.id);
      }

      queryClient.invalidateQueries({ queryKey: ['comparisons'] });
    },
  });
}

export function useRecordComparison() {
  const { recordComparison: updateComparisonState } = useComparisonStore();

  return useMutation({
    mutationFn: (request: RecordComparisonRequest) => recordComparison(request),
    onSuccess: (response) => {
      updateComparisonState(response.pair, response.progress);

      // Prefetch waveforms for the new pair
      if (response.pair) {
        prefetchWaveform(response.pair.track_a.id);
        prefetchWaveform(response.pair.track_b.id);
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