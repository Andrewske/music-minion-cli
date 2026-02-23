---
task: 04-genre-selection-modal
status: pending
depends: [03-frontend-api-state]
files:
  - path: web/frontend/src/components/GenreSelectionModal.tsx
    action: create
  - path: web/frontend/src/components/ClickableGenre.tsx
    action: create
  - path: web/frontend/src/components/TrackCard.tsx
    action: modify
---

# Genre Selection Modal & Clickable Genre Tags

## Context
Core feature 1: Click any genre tag to open a modal for multi-genre selection with priority ordering. First selected = primary genre written to file metadata.

## Files to Modify/Create
- `web/frontend/src/components/GenreSelectionModal.tsx` (new)
- `web/frontend/src/components/ClickableGenre.tsx` (new)
- `web/frontend/src/components/TrackCard.tsx` (modify)

## Implementation Details

### GenreSelectionModal.tsx

Follow `SkippedTracksDialog.tsx` Radix Dialog pattern:

```typescript
import * as Dialog from '@radix-ui/react-dialog';
import { useState, useEffect } from 'react';
import { X } from 'lucide-react';
import { useGenreStore } from '../stores/genreStore';
import { getTrackGenres, updateTrackGenres } from '../api/genres';
import type { TrackInfo } from '../types';
import type { TrackGenre } from '../api/genres';
import { EmojiDisplay } from './EmojiDisplay';

interface GenreSelectionModalProps {
  open: boolean;
  onClose: () => void;
  track: TrackInfo;
  onSave?: (track: TrackInfo) => void;
}

export function GenreSelectionModal({ open, onClose, track, onSave }: GenreSelectionModalProps) {
  const { genres, fetchGenres } = useGenreStore();
  const [selectedIds, setSelectedIds] = useState<number[]>([]);  // Ordered by selection
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);

  // Load genres and track's current genres
  useEffect(() => {
    if (open) {
      Promise.all([
        fetchGenres(),
        getTrackGenres(track.id),
      ]).then(([_, trackGenres]) => {
        // Initialize with track's current genres in order
        setSelectedIds(trackGenres.map(g => g.id));
        setIsLoading(false);
      });
    }
  }, [open, track.id]);

  const handleToggleGenre = (genreId: number) => {
    setSelectedIds(prev => {
      if (prev.includes(genreId)) {
        // Deselect
        return prev.filter(id => id !== genreId);
      } else {
        // Select (append to end)
        return [...prev, genreId];
      }
    });
  };

  const handleSave = async () => {
    setIsSaving(true);
    try {
      await updateTrackGenres(track.id, selectedIds);
      onSave?.({ ...track, genre: genres.find(g => g.id === selectedIds[0])?.name });
      onClose();
    } catch (err) {
      console.error('Failed to save genres:', err);
    } finally {
      setIsSaving(false);
    }
  };

  // Separate selected vs available
  const selectedGenres = selectedIds.map(id => genres.find(g => g.id === id)).filter(Boolean);
  const availableGenres = genres
    .filter(g => !selectedIds.includes(g.id))
    .sort((a, b) => b.track_count - a.track_count);

  return (
    <Dialog.Root open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/80" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 -translate-x-1/2 -translate-y-1/2 w-full max-w-md bg-obsidian-surface p-6 max-h-[80vh] overflow-y-auto">
          <Dialog.Title className="text-lg font-semibold text-white mb-4">
            Select Genres
          </Dialog.Title>
          <Dialog.Description className="text-sm text-white/60 mb-4">
            Click to select. First selected = primary genre.
          </Dialog.Description>

          {isLoading ? (
            <div className="text-white/60">Loading...</div>
          ) : (
            <>
              {/* Selected genres with numbered badges */}
              {selectedGenres.length > 0 && (
                <div className="mb-4">
                  <h3 className="text-sm text-white/60 mb-2">Selected</h3>
                  <div className="flex flex-wrap gap-2">
                    {selectedGenres.map((genre, idx) => (
                      <button
                        key={genre.id}
                        onClick={() => handleToggleGenre(genre.id)}
                        className="flex items-center gap-1 px-3 py-1 bg-obsidian-accent text-white text-sm"
                      >
                        <span className="w-5 h-5 bg-white/20 rounded-full text-xs flex items-center justify-center">
                          {idx + 1}
                        </span>
                        {genre.emoji_id && <EmojiDisplay emojiId={genre.emoji_id} size="sm" />}
                        {genre.name}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Available genres sorted by track count */}
              <div>
                <h3 className="text-sm text-white/60 mb-2">Available ({availableGenres.length})</h3>
                <div className="flex flex-wrap gap-2 max-h-60 overflow-y-auto">
                  {availableGenres.map((genre) => (
                    <button
                      key={genre.id}
                      onClick={() => handleToggleGenre(genre.id)}
                      className="flex items-center gap-1 px-3 py-1 bg-obsidian-border hover:bg-obsidian-border/80 text-white/80 text-sm"
                    >
                      {genre.emoji_id && <EmojiDisplay emojiId={genre.emoji_id} size="sm" />}
                      {genre.name}
                      <span className="text-white/40 text-xs">({genre.track_count})</span>
                    </button>
                  ))}
                </div>
              </div>
            </>
          )}

          {/* Footer */}
          <div className="flex justify-end gap-2 mt-6">
            <button
              onClick={onClose}
              className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={isSaving}
              className="px-4 py-2 bg-obsidian-accent hover:bg-obsidian-accent/80 text-white disabled:opacity-50"
            >
              {isSaving ? 'Saving...' : 'Save'}
            </button>
          </div>

          <Dialog.Close asChild>
            <button className="absolute top-4 right-4 text-white/60 hover:text-white">
              <X size={20} />
            </button>
          </Dialog.Close>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
```

### ClickableGenre.tsx

```typescript
import { useState } from 'react';
import type { TrackInfo } from '../types';
import { GenreSelectionModal } from './GenreSelectionModal';
import { EmojiDisplay } from './EmojiDisplay';

interface ClickableGenreProps {
  track: TrackInfo;
  className?: string;
  onTrackUpdate?: (track: TrackInfo) => void;
}

export function ClickableGenre({ track, className, onTrackUpdate }: ClickableGenreProps) {
  const [modalOpen, setModalOpen] = useState(false);

  // TODO: Get emoji from genre if assigned (may need to fetch or pass in)
  const genreEmoji = null; // Placeholder

  return (
    <>
      <button
        onClick={() => setModalOpen(true)}
        className={`hover:text-white hover:underline cursor-pointer ${className}`}
      >
        {genreEmoji && <EmojiDisplay emojiId={genreEmoji} size="sm" />}
        {track.genre ?? 'Unknown genre'}
      </button>

      <GenreSelectionModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        track={track}
        onSave={onTrackUpdate}
      />
    </>
  );
}
```

### TrackCard.tsx Update

Replace line 128:

```typescript
// Before:
<span>{track.genre ?? 'Unknown genre'}</span>

// After:
<ClickableGenre
  track={track}
  onTrackUpdate={onTrackUpdate}  // May need to add this prop to TrackCard
/>
```

## Verification

1. Start app: `uv run music-minion --web`
2. Open http://localhost:5173
3. Navigate to any view with tracks (Home, Playlist, etc.)
4. Click on a genre tag
5. Verify:
   - Modal opens with all genres
   - Selected genres show at top with numbered badges
   - Available genres sorted by track count
   - Can select/deselect genres
   - Save persists changes
   - Primary genre (position 1) shows on track card
