import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'react-toastify';
import * as bucketsApi from '../api/buckets';
import type { BucketRatingApplied, BucketRatingError, BucketRatingPreview } from '../api/buckets';
import { AppliedRatingToast } from '../components/organizer/AppliedRatingToast';

const previewKey = (bucketId: string): readonly ['bucket-rating-preview', string] =>
  ['bucket-rating-preview', bucketId] as const;

const isConflict = (error: unknown): boolean =>
  error instanceof Error && (error as Partial<BucketRatingError>).status === 409;

const errorMessage = (error: unknown): string =>
  error instanceof Error ? error.message : String(error);

interface UseBucketRatingReturn {
  preview: BucketRatingPreview | undefined;
  isPreviewLoading: boolean;
  previewError: Error | null;
  /** Resolves true when applied; false on a stale preview (already refetched). */
  apply: () => Promise<boolean>;
  isApplying: boolean;
}

/**
 * "Apply rating" for one bucket: preview, apply, and an undo toast. Ratings land
 * in the organized playlist, so its track caches are invalidated after apply and
 * undo. The preview waits while a reorder is saving (it would read the old
 * order), then fetches once the save lands.
 */
export function useBucketRating(
  bucketId: string,
  playlistId: number,
  open: boolean,
  isReordering: boolean
): UseBucketRatingReturn {
  const queryClient = useQueryClient();

  const previewQuery = useQuery({
    queryKey: previewKey(bucketId),
    queryFn: () => bucketsApi.previewBucketRating(bucketId),
    enabled: open && !isReordering,
    staleTime: 0,
    gcTime: 0,
  });

  const refreshRatings = (): void => {
    queryClient.invalidateQueries({ queryKey: ['playlist', playlistId] });
    queryClient.invalidateQueries({ queryKey: ['playlist-tracks', playlistId] });
  };

  /** Resolves true when undone; on failure the toast stays so Undo can be retried. */
  const undo = async (applicationId: string): Promise<boolean> => {
    try {
      const { restored, skipped } = await bucketsApi.undoBucketRating(applicationId);
      refreshRatings();
      const note = skipped > 0 ? ` (${skipped} kept: compared since)` : '';
      toast.info(`Rating undone for ${restored} tracks${note}`);
      return true;
    } catch (error) {
      toast.error(`Undo failed: ${errorMessage(error)}`);
      return false;
    }
  };

  const applyMutation = useMutation({
    mutationFn: (trackIds: number[]) => bucketsApi.applyBucketRating(bucketId, trackIds),
    onSuccess: (result: BucketRatingApplied) => {
      const applicationId = result.application_id;
      if (applicationId === null) {
        toast.info('Ratings already match this order');
        return;
      }
      refreshRatings();
      toast.success(
        ({ closeToast, toastProps }) => (
          <AppliedRatingToast
            count={result.rows.length}
            onUndo={() => undo(applicationId)}
            onUndone={closeToast}
            onUndoFailed={() => toast.update(toastProps.toastId, { autoClose: false })}
          />
        ),
        { autoClose: 10000 }
      );
    },
  });

  const apply = async (): Promise<boolean> => {
    const trackIds = previewQuery.data?.track_ids;
    if (!trackIds) return false;
    try {
      await applyMutation.mutateAsync(trackIds);
      return true;
    } catch (error) {
      if (!isConflict(error)) throw error;
      toast.info('Bucket changed since the preview. Check the updated ratings.');
      await previewQuery.refetch();
      return false;
    }
  };

  return {
    preview: previewQuery.data,
    isPreviewLoading: previewQuery.isFetching,
    previewError: previewQuery.error,
    apply,
    isApplying: applyMutation.isPending,
  };
}
