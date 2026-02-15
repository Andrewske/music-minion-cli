import { useState, useEffect } from 'react';
import { toast } from 'sonner';
import type { EmojiInfo } from '../api/emojis';
import { getAllEmojis, updateEmojiMetadata, deleteCustomEmoji } from '../api/emojis';
import { EmojiDisplay } from './EmojiDisplay';

export function EmojiSettings(): JSX.Element {
  const [emojis, setEmojis] = useState<EmojiInfo[]>([]);
  const [editingEmoji, setEditingEmoji] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  useEffect(() => {
    async function loadEmojis(): Promise<void> {
      try {
        const data = await getAllEmojis(200, 0);
        setEmojis(data);
      } catch (err) {
        console.error('Failed to load emojis:', err);
        toast.error('Failed to load emojis');
      } finally {
        setIsLoading(false);
      }
    }

    loadEmojis();
  }, []);

  const handleEdit = (emoji: EmojiInfo): void => {
    setEditingEmoji(emoji.emoji_id);
    setEditValue(emoji.custom_name || '');
  };

  const handleSave = async (emojiId: string): Promise<void> => {
    setIsSaving(true);
    try {
      await updateEmojiMetadata(emojiId, editValue.trim() || null);

      // Update local state
      setEmojis(prev => prev.map(e =>
        e.emoji_id === emojiId
          ? { ...e, custom_name: editValue.trim() || null }
          : e
      ));

      setEditingEmoji(null);
      toast.success('Custom name saved');
    } catch (err) {
      console.error('Failed to update emoji:', err);
      toast.error('Failed to save custom name');
    } finally {
      setIsSaving(false);
    }
  };

  const handleCancel = (): void => {
    setEditingEmoji(null);
    setEditValue('');
  };

  const handleKeyDown = (e: React.KeyboardEvent, emojiId: string): void => {
    if (e.key === 'Enter') {
      handleSave(emojiId);
    } else if (e.key === 'Escape') {
      handleCancel();
    }
  };

  const handleDeleteCustom = async (emojiId: string): Promise<void> => {
    if (!confirm('Delete this custom emoji? It will be removed from all tracks.')) {
      return;
    }

    setDeletingId(emojiId);
    try {
      await deleteCustomEmoji(emojiId);
      setEmojis(prev => prev.filter(e => e.emoji_id !== emojiId));
      toast.success('Custom emoji deleted');
    } catch (err) {
      console.error('Failed to delete emoji:', err);
      toast.error('Failed to delete custom emoji');
    } finally {
      setDeletingId(null);
    }
  };

  if (isLoading) {
    return (
      <div className="max-w-4xl mx-auto p-6">
        <h1 className="text-2xl font-bold text-white mb-6">Emoji Settings</h1>
        <div className="text-white/60">Loading emojis...</div>
      </div>
    );
  }

  const customEmojis = emojis.filter(e => e.type === 'custom');
  const unicodeEmojis = emojis.filter(e => e.type === 'unicode');

  return (
    <div className="max-w-4xl mx-auto p-6">
      <h1 className="text-2xl font-bold text-white mb-6">Emoji Settings</h1>

      {/* Custom Emojis Section */}
      <div className="mb-8">
        <h2 className="text-lg font-semibold text-white mb-3">Your Custom Emojis</h2>
        <p className="text-sm text-white/60 mb-4">
          To add custom emojis, use the CLI script:{' '}
          <code className="bg-obsidian-border px-2 py-1 text-xs">
            uv run scripts/add-custom-emoji.py --image path/to/emoji.png --name "my emoji"
          </code>
        </p>

        {customEmojis.length === 0 ? (
          <div className="bg-obsidian-surface p-6 text-center text-white/50">
            No custom emojis yet. Use the CLI script above to add some!
          </div>
        ) : (
          <div className="grid grid-cols-4 md:grid-cols-6 lg:grid-cols-8 gap-4">
            {customEmojis.map((emoji) => (
              <div
                key={emoji.emoji_id}
                className="relative bg-obsidian-border p-3 group"
              >
                <div className="flex justify-center">
                  <img
                    src={`/custom_emojis/${emoji.file_path}`}
                    alt={emoji.default_name}
                    className="w-16 h-16 object-contain"
                  />
                </div>
                <p className="text-xs text-white/60 text-center mt-2 truncate">
                  {emoji.custom_name || emoji.default_name}
                </p>

                {/* Delete button */}
                <button
                  onClick={() => handleDeleteCustom(emoji.emoji_id)}
                  disabled={deletingId === emoji.emoji_id}
                  className="absolute top-1 right-1 bg-red-600 hover:bg-red-500 disabled:opacity-50 text-white w-6 h-6 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                  aria-label="Delete"
                >
                  {deletingId === emoji.emoji_id ? '...' : '\u00d7'}
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Unicode Emojis Table */}
      <div>
        <h2 className="text-lg font-semibold text-white mb-3">Unicode Emojis</h2>
        <p className="text-white/60 mb-4">
          Customize emoji names for better searchability. These names appear in search results.
        </p>

        <div className="bg-obsidian-surface overflow-hidden">
          <table className="w-full">
            <thead className="bg-obsidian-border">
              <tr>
                <th className="px-4 py-3 text-left text-sm font-semibold text-white/60">Emoji</th>
                <th className="px-4 py-3 text-left text-sm font-semibold text-white/60">Default Name</th>
                <th className="px-4 py-3 text-left text-sm font-semibold text-white/60">Custom Name</th>
                <th className="px-4 py-3 text-left text-sm font-semibold text-white/60">Uses</th>
                <th className="px-4 py-3 text-left text-sm font-semibold text-white/60">Actions</th>
              </tr>
            </thead>
            <tbody>
              {unicodeEmojis.map((emoji) => (
                <tr key={emoji.emoji_id} className="border-t border-obsidian-border">
                  <td className="px-4 py-3 text-2xl">
                    <EmojiDisplay emojiId={emoji.emoji_id} emojiData={emoji} size="md" />
                  </td>
                  <td className="px-4 py-3 text-sm text-white/60">{emoji.default_name}</td>
                  <td className="px-4 py-3">
                    {editingEmoji === emoji.emoji_id ? (
                      <input
                        type="text"
                        value={editValue}
                        onChange={(e) => setEditValue(e.target.value)}
                        onKeyDown={(e) => handleKeyDown(e, emoji.emoji_id)}
                        className="w-full px-2 py-1 bg-obsidian-border text-white border border-slate-600 focus:border-obsidian-accent focus:outline-none"
                        placeholder="Enter custom name..."
                        autoFocus
                      />
                    ) : (
                      <span className="text-white">
                        {emoji.custom_name || <span className="text-white/50 italic">None</span>}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-sm text-white/60">{emoji.use_count}</td>
                  <td className="px-4 py-3">
                    {editingEmoji === emoji.emoji_id ? (
                      <div className="flex gap-2">
                        <button
                          onClick={() => handleSave(emoji.emoji_id)}
                          disabled={isSaving}
                          className="px-3 py-1 bg-obsidian-accent hover:bg-obsidian-accent disabled:opacity-50 text-sm text-white"
                        >
                          {isSaving ? 'Saving...' : 'Save'}
                        </button>
                        <button
                          onClick={handleCancel}
                          disabled={isSaving}
                          className="px-3 py-1 bg-slate-700 hover:bg-slate-600 disabled:opacity-50 text-sm text-white"
                        >
                          Cancel
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={() => handleEdit(emoji)}
                        className="px-3 py-1 bg-slate-700 hover:bg-slate-600 text-sm text-white"
                      >
                        Edit
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
