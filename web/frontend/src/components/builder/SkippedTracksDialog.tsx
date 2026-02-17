import * as Dialog from '@radix-ui/react-dialog';
import { X } from 'lucide-react';
import type { Track } from '../../api/builder';

interface SkippedTracksDialogProps {
  open: boolean;
  onClose: () => void;
  tracks: Track[];
  onUnskip: (trackId: number) => void;
  isUnskipping?: boolean;
}

const formatSkippedAt = (skippedAt: string | undefined): string => {
  if (!skippedAt) return 'Unknown';
  const date = new Date(skippedAt);
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit'
  });
};

export function SkippedTracksDialog({
  open,
  onClose,
  tracks,
  onUnskip,
  isUnskipping = false,
}: SkippedTracksDialogProps): JSX.Element {
  return (
    <Dialog.Root open={open} onOpenChange={onClose}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/80 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0" />
        <Dialog.Content className="fixed left-[50%] top-[50%] z-50 translate-x-[-50%] translate-y-[-50%] bg-slate-900 border border-slate-700 rounded-lg shadow-xl w-full max-w-3xl max-h-[80vh] overflow-hidden">
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-slate-700">
            <Dialog.Title className="text-xl font-semibold text-white">
              Skipped Tracks ({tracks.length})
            </Dialog.Title>
            <Dialog.Close asChild>
              <button
                className="rounded-sm opacity-70 ring-offset-slate-950 transition-opacity hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-slate-400 focus:ring-offset-2 disabled:pointer-events-none"
                aria-label="Close"
              >
                <X className="h-5 w-5 text-slate-400" />
              </button>
            </Dialog.Close>
          </div>

          {/* Content */}
          <div className="overflow-y-auto max-h-[calc(80vh-120px)]">
            {tracks.length === 0 ? (
              <div className="px-6 py-12 text-center">
                <p className="text-slate-400 text-lg">No skipped tracks</p>
              </div>
            ) : (
              <div className="divide-y divide-slate-800">
                {tracks.map((track) => (
                  <div
                    key={track.id}
                    className="px-6 py-4 hover:bg-slate-800/50 transition-colors flex items-center justify-between"
                  >
                    <div className="flex-1 min-w-0">
                      <div className="text-white font-medium truncate">
                        {track.title}
                      </div>
                      <div className="text-slate-400 text-sm truncate">
                        {track.artist}
                      </div>
                      <div className="text-slate-500 text-xs mt-1">
                        Skipped: {formatSkippedAt((track as Track & { skipped_at?: string }).skipped_at)}
                      </div>
                    </div>
                    <button
                      onClick={() => onUnskip(track.id)}
                      disabled={isUnskipping}
                      className="ml-4 px-4 py-2 bg-purple-600 hover:bg-purple-700 disabled:bg-slate-700 disabled:text-slate-500 text-white rounded transition-colors text-sm font-medium whitespace-nowrap"
                    >
                      Restore
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
