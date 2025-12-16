import { useMutation, useQueryClient } from '@tanstack/react-query';
import { startSession, recordComparison } from '../api/comparisons';
import { archiveTrack, prefetchWaveform } from '../api/tracks';
import { useComparisonStore } from '../stores/comparisonStore';
import type { StartSessionRequest, RecordComparisonRequest } from '../types';

export function useStartSession() {
  const queryClient = useQueryClient();
  const { setSession } = useComparisonStore();

  return useMutation({
    mutationFn: (request: StartSessionRequest) => startSession(request),
    onSuccess: (response, request) => {
      setSession(
        response.session_id,
        response.pair,
        response.prefetched_pair,
        request.priority_path_prefix,
        request.ranking_mode === 'playlist' ? 'playlist' : 'global',
        request.playlist_id ?? null
      );

      // Prefetch waveforms for current and prefetched pairs
      prefetchWaveform(response.pair.track_a.id);
      prefetchWaveform(response.pair.track_b.id);
      if (response.prefetched_pair) {
        prefetchWaveform(response.prefetched_pair.track_a.id);
        prefetchWaveform(response.prefetched_pair.track_b.id);
      }

      queryClient.invalidateQueries({ queryKey: ['comparisons'] });
    },
  });
}

export function useRecordComparison() {
  const { incrementCompleted, setNextPairForComparison } = useComparisonStore();

  return useMutation({
    mutationFn: (request: RecordComparisonRequest) => recordComparison(request),
    onSuccess: (response) => {
      if (response.success) {
        incrementCompleted();

        // Update pair for comparison but keep current track playing
        if (response.next_pair) {
          setNextPairForComparison(response.next_pair, response.prefetched_pair);

          // Prefetch waveforms for the new pair
          prefetchWaveform(response.next_pair.track_a.id);
          prefetchWaveform(response.next_pair.track_b.id);
          if (response.prefetched_pair) {
            prefetchWaveform(response.prefetched_pair.track_a.id);
            prefetchWaveform(response.prefetched_pair.track_b.id);
          }
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