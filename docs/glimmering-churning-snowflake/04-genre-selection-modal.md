---
task: 04-genre-selection-modal
status: pending
depends:
  - 03-frontend-api-store
files:
  - path: web/frontend/src/components/GenreSelectionModal.tsx
    action: create
  - path: web/frontend/src/components/GenreTag.tsx
    action: create
  - path: web/frontend/src/components/TrackCard.tsx
    action: modify
---

# Genre Selection Modal & TrackCard Integration

## Context
Modal for selecting/ordering genres per track. GenreTag component for display. TrackCard shows primary genre only.

## Files to Modify/Create
- `web/frontend/src/components/GenreSelectionModal.tsx` (new)
- `web/frontend/src/components/GenreTag.tsx` (new)
- `web/frontend/src/components/TrackCard.tsx` (modify)

## Implementation Details

### 1. Create `GenreTag.tsx`

```tsx
interface GenreTagProps {
  genre: {
    name: string;
    emoji_id?: string | null;
  };
  onClick?: () => void;
  className?: string;
}

export function GenreTag({ genre, onClick, className = '' }: GenreTagProps): JSX.Element {
  const content = (
    <>
      {genre.emoji_id && <span className="mr-1">{genre.emoji_id}</span>}
      <span>{genre.name}</span>
    </>
  );

  if (onClick) {
    return (
      <button
        type="button"
        onClick={onClick}
        className={`inline-flex items-center hover:text-white/80 transition-colors ${className}`}
      >
        {content}
      </button>
    );
  }

  return (
    <span className={`inline-flex items-center ${className}`}>
      {content}
    </span>
  );
}
```

### 2. Create `GenreSelectionModal.tsx`

Follow `SkippedTracksDialog.tsx` Radix Dialog pattern:

```tsx
import * as Dialog from '@radix-ui/react-dialog';
import { useState, useEffect } from 'react';
import { X } from 'lucide-react';
import { useGenreStore } from '../stores/genreStore';
import { updateTrackGenres, type TrackGenre } from '../api/genres';
import type { Track } from '../api/tracks';

interface GenreSelectionModalProps {
  open: boolean;
  onClose: () => void;
  track: Track;
  onSave: (genres: TrackGenre[]) => void;
}

export function GenreSelectionModal({
  open,
  onClose,
  track,
  onSave,
}: GenreSelectionModalProps): JSX.Element {
  const { genres, fetchGenres } = useGenreStore();
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (open) {
      fetchGenres();
      // Initialize with current track genres in order
      setSelectedIds(track.genres?.map((g) => g.id) ?? []);
    }
  }, [open, track.genres, fetchGenres]);

  const handleToggle = (genreId: number) => {
    setSelectedIds((prev) => {
      if (prev.includes(genreId)) {
        return prev.filter((id) => id !== genreId);
      }
      return [...prev, genreId];
    });
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const updated = await updateTrackGenres(track.id, selectedIds);
      onSave(updated);
      onClose();
    } finally {
      setSaving(false);
    }
  };

  const selectedGenres = selectedIds
    .map((id) => genres.find((g) => g.id === id))
    .filter(Boolean);

  const availableGenres = genres
    .filter((g) => !selectedIds.includes(g.id))
    .sort((a, b) => b.track_count - a.track_count);

  return (
    <Dialog.Root open={open} onOpenChange={(o) => !o && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/60 backdrop-blur-sm" />
        <Dialog.Content className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-zinc-900 rounded-lg p-6 w-full max-w-md max-h-[80vh] overflow-y-auto">
          <Dialog.Title className="text-lg font-semibold mb-4">
            Select Genres
          </Dialog.Title>

          {/* Selected genres with position badges */}
          {selectedGenres.length > 0 && (
            <div className="mb-4">
              <div className="text-sm text-white/50 mb-2">Selected (click to remove)</div>
              <div className="flex flex-wrap gap-2">
                {selectedGenres.map((genre, idx) => (
                  <button
                    key={genre!.id}
                    onClick={() => handleToggle(genre!.id)}
                    className="flex items-center gap-1 px-3 py-1 bg-white/10 rounded-full hover:bg-white/20"
                  >
                    <span className="text-xs bg-white/20 rounded-full w-5 h-5 flex items-center justify-center">
                      {idx + 1}
                    </span>
                    {genre!.emoji_id && <span>{genre!.emoji_id}</span>}
                    <span>{genre!.name}</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Available genres */}
          <div className="mb-4">
            <div className="text-sm text-white/50 mb-2">Available</div>
            <div className="flex flex-wrap gap-2">
              {availableGenres.map((genre) => (
                <button
                  key={genre.id}
                  onClick={() => handleToggle(genre.id)}
                  className="flex items-center gap-1 px-3 py-1 bg-zinc-800 rounded-full hover:bg-zinc-700"
                >
                  {genre.emoji_id && <span>{genre.emoji_id}</span>}
                  <span>{genre.name}</span>
                  <span className="text-xs text-white/30">({genre.track_count})</span>
                </button>
              ))}
            </div>
          </div>

          {/* Actions */}
          <div className="flex justify-end gap-2 mt-6">
            <button
              onClick={onClose}
              className="px-4 py-2 text-white/70 hover:text-white"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={saving}
              className="px-4 py-2 bg-white/10 rounded hover:bg-white/20 disabled:opacity-50"
            >
              {saving ? 'Saving...' : 'Save'}
            </button>
          </div>

          <Dialog.Close asChild>
            <button
              className="absolute top-4 right-4 text-white/50 hover:text-white"
              aria-label="Close"
            >
              <X size={20} />
            </button>
          </Dialog.Close>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
```

### 3. Update `TrackCard.tsx`

Replace the genre span (around line 128) with GenreTag:

```tsx
import { useState } from 'react';
import { GenreTag } from './GenreTag';
import { GenreSelectionModal } from './GenreSelectionModal';

// Inside TrackCard component:
const [genreModalOpen, setGenreModalOpen] = useState(false);

// Get primary genre (position=1 or first in array, or fall back to genre string)
const primaryGenre = track.genres?.[0] ?? (track.genre ? { name: track.genre, emoji_id: null } : null);

// In the render:
{primaryGenre ? (
  <>
    <GenreTag
      genre={primaryGenre}
      onClick={onTrackUpdate ? () => setGenreModalOpen(true) : undefined}
    />
    {onTrackUpdate && (
      <GenreSelectionModal
        open={genreModalOpen}
        onClose={() => setGenreModalOpen(false)}
        track={track}
        onSave={(genres) => {
          onTrackUpdate({ ...track, genres });
        }}
      />
    )}
  </>
) : (
  <span className="text-white/30">No genre</span>
)}
```

## Verification
- Start app: `uv run music-minion --web`
- Open http://localhost:5173
- Find a track with a genre
- Click the genre text → modal should open
- Select/deselect genres, verify order changes
- Save → track should update
