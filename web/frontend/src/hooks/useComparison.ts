import { useMutation, useQueryClient } from '@tanstack/react-query';
import { startComparison, recordComparison } from '../api/comparisons';
import { archiveTrack, prefetchWaveform } from '../api/tracks';
import { useComparisonStore } from '../stores/comparisonStore';
import { usePlayerStore } from '../stores/playerStore';
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
  const { play } = usePlayerStore();

  return useMutation({
    mutationFn: (request: RecordComparisonRequest) => recordComparison(request),
    onSuccess: (response) => {
      updateComparisonState(response.pair, response.progress);

      // Auto-play track A of next comparison if enabled
      // Read from store directly to avoid stale closure
      if (useComparisonStore.getState().autoplay && response.pair) {
        const trackIds = [response.pair.track_a.id, response.pair.track_b.id];
        play(response.pair.track_a, { type: 'comparison', track_ids: trackIds, shuffle: false });
      }

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