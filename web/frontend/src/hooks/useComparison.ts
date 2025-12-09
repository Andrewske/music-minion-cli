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
      setSession(response.session_id, response.pair, 15); // TODO: Use response target
      // Invalidate any cached comparison data
      queryClient.invalidateQueries({ queryKey: ['comparisons'] });
    },
  });
}

export function useRecordComparison() {
  const { incrementCompleted, setCurrentPair } = useComparisonStore();

  return useMutation({
    mutationFn: (request: RecordComparisonRequest) => recordComparison(request),
    onSuccess: (response) => {
      if (response.success) {
        console.log('✅ Comparison recorded successfully:', {
          comparisons_done: response.comparisons_done,
          target: response.target_comparisons,
          has_next_pair: !!response.next_pair,
          session_complete: response.session_complete,
        });

        incrementCompleted();

        // If there's a next pair, update the store
        if (response.next_pair) {
          setCurrentPair(response.next_pair);
          console.log('📋 Next pair loaded:', {
            track_a: response.next_pair.track_a.title,
            track_b: response.next_pair.track_b.title,
          });
        } else {
          console.log('🎉 Session complete - no more pairs');
        }
      } else {
        console.error('❌ Comparison recording failed - success=false in response');
      }
    },
    onError: (error) => {
      console.error('❌ Comparison API call failed:', error);
    },
  });
}

export function useArchiveTrack() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (trackId: number) => archiveTrack(trackId),
    onSuccess: () => {
      console.log('✅ Track archived successfully');
      // Invalidate comparison queries to refresh available tracks
      queryClient.invalidateQueries({ queryKey: ['comparisons'] });
    },
    onError: (error) => {
      console.error('❌ Archive API call failed:', error);
    },
  });
}