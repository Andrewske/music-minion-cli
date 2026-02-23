import { useState, useEffect } from 'react';
import { Trash2, Check, X } from 'lucide-react';
import { useGenreStore } from '../../stores/genreStore';
import {
  renameGenre,
  deleteGenre,
  assignGenreEmoji,
  type GenreInfo,
} from '../../api/genres';
import { EmojiPicker } from '../EmojiPicker';
import { toast } from 'sonner';

export function GenreSettingsSection(): JSX.Element {
  const { genres, fetchGenres, updateGenre, removeGenre } = useGenreStore();
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editValue, setEditValue] = useState('');
  const [emojiPickerFor, setEmojiPickerFor] = useState<number | null>(null);

  useEffect(() => {
    fetchGenres();
  }, [fetchGenres]);

  const handleStartEdit = (genre: GenreInfo): void => {
    setEditingId(genre.id);
    setEditValue(genre.name);
  };

  const handleSaveEdit = async (genreId: number): Promise<void> => {
    if (!editValue.trim()) {
      toast.error('Genre name cannot be empty');
      return;
    }

    try {
      const updated = await renameGenre(genreId, editValue.trim());
      updateGenre(updated);

      // Check if it was a merge (id changed)
      if (updated.id !== genreId) {
        removeGenre(genreId);
        toast.success(`Merged into "${updated.name}"`);
      } else {
        toast.success('Genre renamed');
      }
    } catch (err) {
      toast.error('Failed to rename genre');
    } finally {
      setEditingId(null);
      setEditValue('');
    }
  };

  const handleDelete = async (genre: GenreInfo): Promise<void> => {
    if (genre.track_count > 0) {
      toast.error(`Cannot delete: ${genre.track_count} tracks use this genre`);
      return;
    }

    try {
      await deleteGenre(genre.id);
      removeGenre(genre.id);
      toast.success('Genre deleted');
    } catch (err) {
      toast.error('Failed to delete genre');
    }
  };

  const handleEmojiSelect = async (genreId: number, emojiId: string | null): Promise<void> => {
    try {
      const updated = await assignGenreEmoji(genreId, emojiId);
      updateGenre(updated);
      toast.success(emojiId ? 'Emoji assigned' : 'Emoji removed');
    } catch (err) {
      toast.error('Failed to update emoji');
    } finally {
      setEmojiPickerFor(null);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent, genreId: number): void => {
    if (e.key === 'Enter') {
      handleSaveEdit(genreId);
    } else if (e.key === 'Escape') {
      setEditingId(null);
      setEditValue('');
    }
  };

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold">Genres</h2>
      <p className="text-sm text-white/60">
        Rename, merge, or assign emojis to genres. Renaming to an existing name merges them.
      </p>

      <div className="border border-white/10 rounded-lg overflow-hidden">
        <table className="w-full">
          <thead className="bg-white/5">
            <tr>
              <th className="text-left px-4 py-2 text-sm font-medium text-white/70">Name</th>
              <th className="text-center px-4 py-2 text-sm font-medium text-white/70 w-20">Tracks</th>
              <th className="text-center px-4 py-2 text-sm font-medium text-white/70 w-20">Emoji</th>
              <th className="w-12"></th>
            </tr>
          </thead>
          <tbody>
            {genres.map((genre) => (
              <tr key={genre.id} className="border-t border-white/5 hover:bg-white/5">
                <td className="px-4 py-2">
                  {editingId === genre.id ? (
                    <div className="flex items-center gap-2">
                      <input
                        type="text"
                        value={editValue}
                        onChange={(e) => setEditValue(e.target.value)}
                        onKeyDown={(e) => handleKeyDown(e, genre.id)}
                        className="flex-1 bg-white/10 px-2 py-1 rounded text-sm"
                        autoFocus
                      />
                      <button
                        onClick={() => handleSaveEdit(genre.id)}
                        className="text-green-400 hover:text-green-300"
                      >
                        <Check size={16} />
                      </button>
                      <button
                        onClick={() => setEditingId(null)}
                        className="text-white/50 hover:text-white"
                      >
                        <X size={16} />
                      </button>
                    </div>
                  ) : (
                    <button
                      onClick={() => handleStartEdit(genre)}
                      className="text-left hover:text-white/80"
                    >
                      {genre.name}
                    </button>
                  )}
                </td>
                <td className="text-center px-4 py-2 text-sm text-white/60">
                  {genre.track_count}
                </td>
                <td className="text-center px-4 py-2">
                  <button
                    onClick={() => setEmojiPickerFor(genre.id)}
                    className="text-lg hover:bg-white/10 px-2 py-1 rounded"
                  >
                    {genre.emoji_id ?? '➕'}
                  </button>
                  {emojiPickerFor === genre.id && (
                    <EmojiPicker
                      onSelect={(emojiId) => handleEmojiSelect(genre.id, emojiId)}
                      onClose={() => setEmojiPickerFor(null)}
                      allowClear={!!genre.emoji_id}
                    />
                  )}
                </td>
                <td className="px-2">
                  <button
                    onClick={() => handleDelete(genre)}
                    disabled={genre.track_count > 0}
                    className="text-red-400 hover:text-red-300 disabled:text-white/20 disabled:cursor-not-allowed p-1"
                    title={genre.track_count > 0 ? `${genre.track_count} tracks use this genre` : 'Delete genre'}
                  >
                    <Trash2 size={16} />
                  </button>
                </td>
              </tr>
            ))}
            {genres.length === 0 && (
              <tr>
                <td colSpan={4} className="text-center py-8 text-white/40">
                  No genres found
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
