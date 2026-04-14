import type { ReactElement } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import type { ArtistStats } from '../../api/artists';
import { Button } from '../ui/button';

export interface ConfirmUnfollowDialogProps {
  artist: ArtistStats | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => void;
  isPending: boolean;
}

function buildEventCountText(artist: ArtistStats): string {
  const est = Math.round(artist.feed_noise_30d * 30);
  if (est <= 0) return 'delete recorded feed events';
  return `delete ~${est.toLocaleString()} recorded feed events`;
}

export function ConfirmUnfollowDialog({
  artist,
  open,
  onOpenChange,
  onConfirm,
  isPending,
}: ConfirmUnfollowDialogProps): ReactElement {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0" />
        <Dialog.Content className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-50 w-full max-w-md bg-obsidian-surface border border-obsidian-border p-6 space-y-4 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0">
          <Dialog.Title className="font-inter text-lg font-semibold text-white">
            Unfollow {artist?.display_name ?? ''}?
          </Dialog.Title>

          <Dialog.Description className="font-inter text-sm text-white/70 leading-relaxed">
            This will unfollow this artist on SoundCloud and{' '}
            {artist !== null ? buildEventCountText(artist) : 'delete recorded feed events'}.
            Your ratings, ELO, and playlist memberships are preserved.
          </Dialog.Description>

          <div className="flex justify-end gap-2 pt-2 border-t border-obsidian-border">
            <Button
              variant="ghost"
              className="text-white/60 hover:text-white"
              onClick={() => onOpenChange(false)}
              disabled={isPending}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={onConfirm}
              disabled={isPending}
            >
              {isPending ? 'Unfollowing…' : 'Unfollow'}
            </Button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
