---
task: 05-genre-settings-page
status: pending
depends: [03-frontend-api-state]
files:
  - path: web/frontend/src/components/Settings/GenreSettingsSection.tsx
    action: create
  - path: web/frontend/src/components/Settings/SettingsPage.tsx
    action: modify
  - path: web/frontend/src/routes/settings.tsx
    action: modify
---

# Genre Settings Page

## Context
Core feature 2: Settings page for mass genre management. Rename/merge genres, assign emojis that propagate to all tracks.

## Files to Modify/Create
- `web/frontend/src/components/Settings/GenreSettingsSection.tsx` (new)
- `web/frontend/src/components/Settings/SettingsPage.tsx` (modify)
- `web/frontend/src/routes/settings.tsx` (modify)

## Implementation Details

### GenreSettingsSection.tsx

Follow `EmojiSettingsSection.tsx` pattern:

```typescript
import { useState, useEffect } from 'react';
import { toast } from 'sonner';
import { useGenreStore } from '../../stores/genreStore';
import { renameGenre, assignGenreEmoji, deleteGenre } from '../../api/genres';
import { EmojiDisplay } from '../EmojiDisplay';
import { EmojiPicker } from '../EmojiPicker';

export function GenreSettingsSection(): JSX.Element {
  const { genres, fetchGenres, updateGenre, removeGenre } = useGenreStore();
  const [isLoading, setIsLoading] = useState(true);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editValue, setEditValue] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [emojiPickerOpen, setEmojiPickerOpen] = useState<number | null>(null);

  useEffect(() => {
    fetchGenres().then(() => setIsLoading(false));
  }, []);

  const handleEdit = (genre: { id: number; name: string }) => {
    setEditingId(genre.id);
    setEditValue(genre.name);
  };

  const handleSave = async (genreId: number) => {
    const newName = editValue.trim();
    if (!newName) return;

    // Check if name exists (merge warning)
    const existing = genres.find(g => g.name.toLowerCase() === newName.toLowerCase() && g.id !== genreId);
    if (existing) {
      if (!confirm(`"${newName}" already exists with ${existing.track_count} tracks. Merge genres?`)) {
        return;
      }
    }

    setIsSaving(true);
    try {
      const updated = await renameGenre(genreId, newName);

      if (existing) {
        // Merge happened - remove old genre from UI, update existing
        removeGenre(genreId);
        updateGenre(existing.id, { track_count: updated.track_count });
        toast.success(`Merged into "${newName}"`);
      } else {
        updateGenre(genreId, { name: newName });
        toast.success('Genre renamed');
      }

      setEditingId(null);
    } catch (err) {
      toast.error('Failed to rename genre');
    } finally {
      setIsSaving(false);
    }
  };

  const handleCancel = () => {
    setEditingId(null);
    setEditValue('');
  };

  const handleKeyDown = (e: React.KeyboardEvent, genreId: number) => {
    if (e.key === 'Enter') handleSave(genreId);
    else if (e.key === 'Escape') handleCancel();
  };

  const handleEmojiSelect = async (genreId: number, emojiId: string) => {
    try {
      await assignGenreEmoji(genreId, emojiId);
      updateGenre(genreId, { emoji_id: emojiId });
      setEmojiPickerOpen(null);
      toast.success('Emoji assigned to genre');
    } catch (err) {
      toast.error('Failed to assign emoji');
    }
  };

  const handleRemoveEmoji = async (genreId: number) => {
    try {
      await assignGenreEmoji(genreId, null);
      updateGenre(genreId, { emoji_id: null });
      toast.success('Emoji removed');
    } catch (err) {
      toast.error('Failed to remove emoji');
    }
  };

  const handleDelete = async (genreId: number, name: string, trackCount: number) => {
    if (!confirm(`Delete "${name}"? This will remove the genre from ${trackCount} tracks.`)) {
      return;
    }

    try {
      await deleteGenre(genreId);
      removeGenre(genreId);
      toast.success('Genre deleted');
    } catch (err) {
      toast.error('Failed to delete genre');
    }
  };

  if (isLoading) {
    return <div className="text-white/60">Loading genres...</div>;
  }

  // Sort by track count
  const sortedGenres = [...genres].sort((a, b) => b.track_count - a.track_count);

  return (
    <div>
      <h2 className="text-lg font-semibold text-white mb-3">Genre Management</h2>
      <p className="text-white/60 mb-4">
        Rename genres to merge them. Assign emojis to apply across all tracks.
      </p>

      <div className="bg-obsidian-surface overflow-hidden">
        <table className="w-full">
          <thead className="bg-obsidian-border">
            <tr>
              <th className="px-4 py-3 text-left text-sm font-semibold text-white/60">Genre</th>
              <th className="px-4 py-3 text-left text-sm font-semibold text-white/60">Tracks</th>
              <th className="px-4 py-3 text-left text-sm font-semibold text-white/60">Emoji</th>
              <th className="px-4 py-3 text-left text-sm font-semibold text-white/60">Actions</th>
            </tr>
          </thead>
          <tbody>
            {sortedGenres.map((genre) => (
              <tr key={genre.id} className="border-t border-obsidian-border">
                <td className="px-4 py-3">
                  {editingId === genre.id ? (
                    <input
                      type="text"
                      value={editValue}
                      onChange={(e) => setEditValue(e.target.value)}
                      onKeyDown={(e) => handleKeyDown(e, genre.id)}
                      className="w-full px-2 py-1 bg-obsidian-border text-white border border-slate-600 focus:border-obsidian-accent focus:outline-none"
                      autoFocus
                    />
                  ) : (
                    <span className="text-white">{genre.name}</span>
                  )}
                </td>
                <td className="px-4 py-3 text-sm text-white/60">{genre.track_count}</td>
                <td className="px-4 py-3 relative">
                  {genre.emoji_id ? (
                    <div className="flex items-center gap-2">
                      <EmojiDisplay emojiId={genre.emoji_id} size="md" />
                      <button
                        onClick={() => handleRemoveEmoji(genre.id)}
                        className="text-red-400 hover:text-red-300 text-xs"
                      >
                        Remove
                      </button>
                    </div>
                  ) : (
                    <button
                      onClick={() => setEmojiPickerOpen(genre.id)}
                      className="text-white/40 hover:text-white text-sm"
                    >
                      + Add emoji
                    </button>
                  )}
                  {emojiPickerOpen === genre.id && (
                    <EmojiPicker
                      onSelect={(emojiId) => handleEmojiSelect(genre.id, emojiId)}
                      onClose={() => setEmojiPickerOpen(null)}
                    />
                  )}
                </td>
                <td className="px-4 py-3">
                  {editingId === genre.id ? (
                    <div className="flex gap-2">
                      <button
                        onClick={() => handleSave(genre.id)}
                        disabled={isSaving}
                        className="px-3 py-1 bg-obsidian-accent hover:bg-obsidian-accent/80 disabled:opacity-50 text-sm text-white"
                      >
                        {isSaving ? 'Saving...' : 'Save'}
                      </button>
                      <button
                        onClick={handleCancel}
                        className="px-3 py-1 bg-slate-700 hover:bg-slate-600 text-sm text-white"
                      >
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <div className="flex gap-2">
                      <button
                        onClick={() => handleEdit(genre)}
                        className="px-3 py-1 bg-slate-700 hover:bg-slate-600 text-sm text-white"
                      >
                        Rename
                      </button>
                      <button
                        onClick={() => handleDelete(genre.id, genre.name, genre.track_count)}
                        className="px-3 py-1 bg-red-700 hover:bg-red-600 text-sm text-white"
                      >
                        Delete
                      </button>
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
```

### SettingsPage.tsx Update

Add 'genres' tab:

```typescript
type SettingsTab = 'youtube' | 'emoji' | 'genres';

// In the tab buttons section, add:
<button
  onClick={() => setActiveTab('genres')}
  className={`px-4 py-2 ${activeTab === 'genres' ? 'bg-obsidian-accent' : 'bg-slate-700'}`}
>
  Genres
</button>

// In the content section, add:
{activeTab === 'genres' && <GenreSettingsSection />}
```

### settings.tsx Update

```typescript
type SettingsSearch = {
  tab?: 'youtube' | 'emoji' | 'genres';
};

export const Route = createFileRoute('/settings')({
  component: SettingsPage,
  validateSearch: (search: Record<string, unknown>): SettingsSearch => {
    const validTabs = ['youtube', 'emoji', 'genres'];
    const tab = search.tab as string;
    return {
      tab: validTabs.includes(tab) ? tab as SettingsSearch['tab'] : 'youtube',
    };
  },
});
```

## Verification

1. Start app: `uv run music-minion --web`
2. Open http://localhost:5173/settings?tab=genres
3. Verify:
   - Genres listed sorted by track count
   - Inline rename works (Enter to save, Escape to cancel)
   - Merge confirmation when renaming to existing
   - Emoji picker assigns emoji
   - Emoji shows on tracks with that genre
   - Delete confirmation and removal
