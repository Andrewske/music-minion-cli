import type { ReactElement } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import type { BulkProgress } from '../../hooks/useUnfollowSuggestions';
import { Button } from '../ui/button';

interface ConfirmProps {
  count: number;
  /** Tiered accounts in the section, left out of the bulk run. */
  skipped: number;
  section: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => void;
}

export function ConfirmBulkDialog({ count, skipped, section, open, onOpenChange, onConfirm }: ConfirmProps): ReactElement {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/80 backdrop-blur-xs z-50" />
        <Dialog.Content className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-50 w-[calc(100%-2rem)] max-w-md bg-obsidian-surface border border-obsidian-border p-6 space-y-4">
          <Dialog.Title className="font-inter text-lg font-semibold text-white">
            Unfollow {count.toLocaleString()} accounts?
          </Dialog.Title>
          <Dialog.Description className="font-inter text-sm text-white/70 leading-relaxed">
            Every untiered account in {section} gets unfollowed on SoundCloud, 10 at a time. You can stop partway.
            Ratings, likes and playlists stay as they are.
            {skipped > 0 && ` ${skipped.toLocaleString()} tiered ${skipped === 1 ? 'artist stays' : 'artists stay'} listed to unfollow one by one.`}
          </Dialog.Description>
          <div className="flex justify-end gap-2 pt-2 border-t border-obsidian-border">
            <Button variant="ghost" className="text-white/60 hover:text-white" onClick={() => onOpenChange(false)}>Cancel</Button>
            <Button variant="destructive" onClick={onConfirm}>Unfollow {count.toLocaleString()}</Button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

export function BulkProgressBar({ progress, stopping, onStop }: { progress: BulkProgress; stopping: boolean; onStop: () => void }): ReactElement {
  const pct = progress.total ? Math.round(((progress.done + progress.failed) / progress.total) * 100) : 0;
  return (
    <div data-testid="bulk-progress" className="mb-4 border border-obsidian-border px-4 py-3 space-y-2">
      <div className="flex items-center justify-between gap-3">
        <p className="font-sf-mono text-xs text-white/70">
          Unfollowed {progress.done.toLocaleString()} / {progress.total.toLocaleString()}
          {progress.failed > 0 && <span className="text-red-400"> · {progress.failed} failed</span>}
        </p>
        <Button size="sm" variant="outline" disabled={stopping} onClick={onStop}>{stopping ? 'Stopping…' : 'Stop'}</Button>
      </div>
      <div className="h-1 bg-obsidian-border">
        <div className="h-1 bg-obsidian-accent transition-all" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
