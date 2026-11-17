import * as Dialog from '@radix-ui/react-dialog';
import { Loader2, X } from 'lucide-react';
import { toast } from 'react-toastify';
import { Button } from '../ui/button';
import type { PlaylistTrackEntry } from '../../types';
import { isNoopRating } from '../../api/buckets';
import type { BucketRatingRow } from '../../api/buckets';
import { methodLabel } from './ratingMethodLabel';
import { useBucketRating } from '../../hooks/useBucketRating';

interface ApplyRatingDialogProps {
  open: boolean;
  onClose: () => void;
  bucketId: string;
  bucketName: string;
  playlistId: number;
  tracks: PlaylistTrackEntry[];
  /** A reorder of this bucket is still saving; apply would race it. */
  isReordering: boolean;
}

export function ApplyRatingDialog({
  open,
  onClose,
  bucketId,
  bucketName,
  playlistId,
  tracks,
  isReordering,
}: ApplyRatingDialogProps): JSX.Element {
  const { preview, isPreviewLoading, previewError, apply, isApplying } = useBucketRating(bucketId, playlistId, open, isReordering);
  const trackById = new Map(tracks.map((t) => [t.id, t]));
  const isNoop = !!preview && isNoopRating(preview);
  const canApply = !!preview && !isNoop && !isPreviewLoading && !isApplying && !isReordering;

  const handleApply = async (): Promise<void> => {
    try {
      if (await apply()) onClose();
    } catch (error) {
      toast.error(`Failed to apply rating to ${bucketName}: ${error instanceof Error ? error.message : String(error)}`);
    }
  };

  return (
    <Dialog.Root open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/60" />
        <Dialog.Content className="fixed left-[50%] top-[50%] z-50 translate-x-[-50%] translate-y-[-50%] bg-obsidian-surface border border-obsidian-border rounded-lg shadow-xl w-[calc(100%-2rem)] max-w-lg max-h-[85vh] flex flex-col overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 border-b border-obsidian-border">
            <Dialog.Title className="text-lg font-semibold text-white">Apply rating: {bucketName}</Dialog.Title>
            <Dialog.Close asChild>
              <button type="button" className="text-white/50 hover:text-white/80" aria-label="Close">
                <X className="w-4 h-4" />
              </button>
            </Dialog.Close>
          </div>
          <Dialog.Description className="px-4 pt-3 text-sm text-white/60">
            {preview ? methodLabel(preview) : 'Top of the bucket gets the highest rating.'}
          </Dialog.Description>

          <div className="flex-1 overflow-y-auto px-4 py-3">
            {previewError && <p className="text-sm text-red-400">{previewError.message}</p>}
            {!preview && !previewError && <Loader2 className="w-5 h-5 animate-spin text-white/40 mx-auto" />}
            {preview && (
              <ol className="divide-y divide-white/5">
                {preview.rows.map((row, i) => (
                  <RatingPreviewRow key={row.track_id} rank={i + 1} row={row} track={trackById.get(row.track_id)} />
                ))}
              </ol>
            )}
          </div>

          <div className="flex items-center justify-end gap-2 px-4 py-3 border-t border-obsidian-border">
            {isReordering && <span className="mr-auto text-xs text-white/40">Saving order…</span>}
            {isNoop && !isReordering && (
              <span className="mr-auto text-xs text-white/40">Ratings already match this order</span>
            )}
            <Button variant="ghost" onClick={onClose}>Cancel</Button>
            <Button onClick={handleApply} disabled={!canApply}>
              {isApplying ? 'Applying…' : 'Apply rating'}
            </Button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

interface RatingPreviewRowProps {
  rank: number;
  row: BucketRatingRow;
  track: PlaylistTrackEntry | undefined;
}

function RatingPreviewRow({ rank, row, track }: RatingPreviewRowProps): JSX.Element {
  const delta = Math.round(row.after - row.before);
  const deltaClass = delta > 0 ? 'text-green-400' : delta < 0 ? 'text-red-400' : 'text-white/30';
  return (
    <li className="flex items-center gap-3 py-1.5 text-sm">
      <span className="w-6 text-right text-white/40 tabular-nums">{rank}</span>
      <span className="flex-1 min-w-0 truncate text-white/90">
        {track ? `${track.artist} - ${track.title}` : `Track ${row.track_id}`}
      </span>
      <span className="text-white/50 tabular-nums">
        {Math.round(row.before)} → {Math.round(row.after)}
      </span>
      <span className={`w-12 text-right tabular-nums ${deltaClass}`}>
        {delta > 0 ? `+${delta}` : delta}
      </span>
    </li>
  );
}
