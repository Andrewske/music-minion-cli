import { useState, useEffect } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { X } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { Button } from '../ui/button';
import { EmojiPicker } from '../EmojiPicker';
import { getPlaylistsByLibrary } from '../../api/playlists';

interface BucketEditDialogProps {
  open: boolean;
  onClose: () => void;
  onSave: (name: string, emojiId?: string) => Promise<void>;
  mode: 'create' | 'edit';
  initialName?: string;
  initialEmojiId?: string;
  parentPlaylistId?: number;
  parentLibrary?: string;
  linkedPlaylistId?: number | null;
  onLink?: (playlistId: number | null) => Promise<void>;
}

export function BucketEditDialog({
  open,
  onClose,
  onSave,
  mode,
  initialName = '',
  initialEmojiId,
  parentPlaylistId,
  parentLibrary,
  linkedPlaylistId,
  onLink,
}: BucketEditDialogProps): JSX.Element {
  const [name, setName] = useState(initialName);
  const [emojiId, setEmojiId] = useState<string | undefined>(initialEmojiId);
  const [showEmojiPicker, setShowEmojiPicker] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [selectedPlaylistId, setSelectedPlaylistId] = useState<string>(
    linkedPlaylistId ? String(linkedPlaylistId) : 'unlink'
  );

  // Fetch playlists for selector (only if editing and parent info provided)
  const { data: playlists } = useQuery({
    queryKey: ['playlists', parentLibrary],
    queryFn: () => getPlaylistsByLibrary(parentLibrary!),
    enabled: mode === 'edit' && !!parentLibrary && !!parentPlaylistId,
  });

  // Filter: same library, exclude parent
  const availablePlaylists = playlists?.filter(
    (p) => p.id !== parentPlaylistId
  ) ?? [];

  // Reset form when dialog opens
  useEffect(() => {
    if (open) {
      setName(initialName);
      setEmojiId(initialEmojiId);
      setSelectedPlaylistId(linkedPlaylistId ? String(linkedPlaylistId) : 'unlink');
    }
  }, [open, initialName, initialEmojiId, linkedPlaylistId]);

  const handleSubmit = async (e: React.FormEvent): Promise<void> => {
    e.preventDefault();
    if (!name.trim()) return;

    setIsSaving(true);
    try {
      await onSave(name.trim(), emojiId);

      // Handle playlist linking (only if editing and onLink provided)
      if (mode === 'edit' && onLink) {
        const newPlaylistId = selectedPlaylistId === 'unlink' ? null : parseInt(selectedPlaylistId, 10);
        const currentPlaylistId = linkedPlaylistId ?? null;

        // Only call onLink if the selection changed
        if (newPlaylistId !== currentPlaylistId) {
          await onLink(newPlaylistId);
        }
      }
    } finally {
      setIsSaving(false);
    }
  };

  const handlePlaylistChange = (e: React.ChangeEvent<HTMLSelectElement>): void => {
    setSelectedPlaylistId(e.target.value);
  };

  const handleEmojiSelect = (selectedEmojiId: string | null): void => {
    setEmojiId(selectedEmojiId ?? undefined);
    setShowEmojiPicker(false);
  };

  const handleRemoveEmoji = (): void => {
    setEmojiId(undefined);
  };

  const title = mode === 'create' ? 'Create Bucket' : 'Edit Bucket';
  const saveLabel = mode === 'create' ? 'Create' : 'Save';

  return (
    <>
      <Dialog.Root open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-50 bg-black/80 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0" />
          <Dialog.Content className="fixed left-[50%] top-[50%] z-50 translate-x-[-50%] translate-y-[-50%] bg-slate-900 border border-slate-700 rounded-lg shadow-xl w-full max-w-md overflow-hidden">
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-700">
              <Dialog.Title className="text-lg font-semibold text-white">
                {title}
              </Dialog.Title>
              <Dialog.Close asChild>
                <button
                  type="button"
                  className="rounded-sm opacity-70 ring-offset-slate-950 transition-opacity hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-slate-400 focus:ring-offset-2 disabled:pointer-events-none"
                  aria-label="Close"
                >
                  <X className="h-5 w-5 text-slate-400" />
                </button>
              </Dialog.Close>
            </div>

            {/* Form */}
            <form onSubmit={handleSubmit}>
              <div className="px-6 py-4 space-y-4">
                {/* Name input */}
                <div>
                  <label
                    htmlFor="bucket-name"
                    className="block text-sm font-medium text-white/70 mb-1.5"
                  >
                    Name <span className="text-red-400">*</span>
                  </label>
                  <input
                    id="bucket-name"
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="e.g., Opening, Peak Time, Cool Down"
                    className="w-full px-3 py-2 bg-slate-800 border border-slate-600 rounded-md text-white placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-obsidian-accent focus:border-transparent"
                  />
                </div>

                {/* Emoji picker */}
                <div>
                  <span
                    id="bucket-emoji-label"
                    className="block text-sm font-medium text-white/70 mb-1.5"
                  >
                    Emoji (optional)
                  </span>
                  <div className="flex items-center gap-2">
                    {emojiId ? (
                      <div className="flex items-center gap-2">
                        <span className="text-2xl">{emojiId}</span>
                        <button
                          type="button"
                          onClick={handleRemoveEmoji}
                          className="text-xs text-white/40 hover:text-white/70 transition-colors"
                        >
                          Remove
                        </button>
                      </div>
                    ) : (
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => setShowEmojiPicker(true)}
                        className="border-slate-600 text-slate-300 hover:text-white"
                      >
                        Choose Emoji
                      </Button>
                    )}
                  </div>
                  <p className="text-xs text-white/40 mt-1.5">
                    If set, the emoji will be automatically added to all tracks in this bucket.
                  </p>
                </div>

                {/* Playlist link selector (only in edit mode) */}
                {mode === 'edit' && parentPlaylistId && parentLibrary && onLink && (
                  <div>
                    <label
                      htmlFor="bucket-playlist-link"
                      className="block text-sm font-medium text-white/70 mb-1.5"
                    >
                      Link to Playlist (optional)
                    </label>
                    <select
                      id="bucket-playlist-link"
                      value={selectedPlaylistId}
                      onChange={handlePlaylistChange}
                      className="w-full px-3 py-2 bg-slate-800 border border-slate-600 rounded-md text-white focus:outline-none focus:ring-2 focus:ring-obsidian-accent focus:border-transparent"
                    >
                      <option value="unlink">Not linked</option>
                      {availablePlaylists.map((p) => (
                        <option key={p.id} value={String(p.id)}>
                          {p.name}
                        </option>
                      ))}
                    </select>
                    <p className="text-xs text-white/40 mt-1.5">
                      Link this bucket to an existing playlist for quick access.
                    </p>
                  </div>
                )}
              </div>

              {/* Footer */}
              <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-slate-700 bg-slate-800/50">
                <Button
                  type="button"
                  variant="ghost"
                  onClick={onClose}
                  disabled={isSaving}
                  className="text-slate-300 hover:text-white"
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  disabled={!name.trim() || isSaving}
                  className="bg-obsidian-accent hover:bg-obsidian-accent/80 disabled:opacity-50"
                >
                  {isSaving ? 'Saving...' : saveLabel}
                </Button>
              </div>
            </form>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>

      {/* Emoji picker overlay */}
      {showEmojiPicker && (
        <EmojiPicker
          onSelect={handleEmojiSelect}
          onClose={() => setShowEmojiPicker(false)}
        />
      )}
    </>
  );
}
