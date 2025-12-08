import { useMutation, useQueryClient } from '@tanstack/react-query';
import { startSession, recordComparison } from '../api/comparisons';
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
        incrementCompleted();

        // If there's a next pair, update the store
        if (response.next_pair) {
          setCurrentPair(response.next_pair);
        }
      }
    },
  });
}