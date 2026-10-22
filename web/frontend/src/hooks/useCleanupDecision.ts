import { useMutation, useQueryClient, type UseMutationResult } from '@tanstack/react-query';
import { toast } from 'sonner';
import {
  decideCleanup,
  type CleanupDecisionRequest,
  type CleanupDecisionResponse,
  type PendingCleanupResponse,
} from '../api/cleanup';
import {
  CLEANUP_COUNT_KEY,
  CLEANUP_DECISION_MUTATION_KEY,
  CLEANUP_PENDING_KEY,
  applyOptimisticDecision,
  rollbackDecision,
  type OptimisticDecision,
} from '../components/cleanup/cleanupView';

type DecisionContext = { removed: OptimisticDecision['removed'] };

const errorText = (error: unknown): string => (error instanceof Error ? error.message : String(error));

/**
 * Apply one Tag review decision. The row leaves the list at once (unclear
 * ones move to the end); on error it goes back where it was.
 */
export function useCleanupDecision(): UseMutationResult<CleanupDecisionResponse, unknown, CleanupDecisionRequest, DecisionContext> {
  const queryClient = useQueryClient();
  return useMutation<CleanupDecisionResponse, unknown, CleanupDecisionRequest, DecisionContext>({
    mutationKey: CLEANUP_DECISION_MUTATION_KEY,
    mutationFn: decideCleanup,
    onMutate: async (request) => {
      await queryClient.cancelQueries({ queryKey: CLEANUP_PENDING_KEY });
      const data = queryClient.getQueryData<PendingCleanupResponse>(CLEANUP_PENDING_KEY);
      if (!data) return { removed: null };
      const next = applyOptimisticDecision(data, request.id, request.verdict);
      queryClient.setQueryData(CLEANUP_PENDING_KEY, next.data);
      return { removed: next.removed };
    },
    onError: (error, request, context) => {
      const removed = context?.removed;
      if (removed) {
        queryClient.setQueryData<PendingCleanupResponse>(CLEANUP_PENDING_KEY, (data) => (data ? rollbackDecision(data, removed) : data));
      }
      void queryClient.invalidateQueries({ queryKey: CLEANUP_COUNT_KEY });
      toast.error(`Could not save ${request.id}: ${errorText(error)}`);
    },
    onSuccess: (response) => {
      queryClient.setQueryData(CLEANUP_COUNT_KEY, { count: response.remaining });
    },
    onSettled: () => {
      // Refetch only once the last in-flight decision lands, so a refetch
      // can't bring back a row whose decision is still on its way.
      if (queryClient.isMutating({ mutationKey: CLEANUP_DECISION_MUTATION_KEY }) <= 1) {
        void queryClient.invalidateQueries({ queryKey: CLEANUP_PENDING_KEY });
      }
    },
  });
}
