import { useEffect, useRef } from 'react';
import Picker from '@emoji-mart/react';
import data from '@emoji-mart/data';
import { useQuery } from '@tanstack/react-query';

interface EmojiPickerProps {
  onSelect: (emojiId: string | null) => void;
  onClose: () => void;
  allowClear?: boolean;
}

interface EmojiMartEmoji {
  id: string;
  name: string;
  native?: string;  // Unicode emoji character
  src?: string;     // Custom emoji image URL
}

/**
 * Emoji picker using emoji-mart with custom emoji support.
 * Wraps emoji-mart in a modal overlay with backdrop click to close.
 */
export function EmojiPicker({ onSelect, onClose, allowClear = false }: EmojiPickerProps): JSX.Element {
  const pickerRef = useRef<HTMLDivElement>(null);

  // Fetch custom emojis from backend in emoji-mart format
  const { data: customEmojis } = useQuery({
    queryKey: ['emojis', 'custom-for-picker'],
    queryFn: async () => {
      const res = await fetch('/api/emojis/custom-picker');
      if (!res.ok) return [];
      return res.json();
    },
  });

  // Close on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  const handleEmojiSelect = (emoji: EmojiMartEmoji) => {
    // For Unicode emojis, use the native character as ID
    // For custom emojis, use the id (UUID)
    const emojiId = emoji.native ?? emoji.id;
    onSelect(emojiId);
    onClose();
  };

  // Build custom category for emoji-mart
  const customCategory = customEmojis?.length
    ? [
        {
          id: 'custom',
          name: 'Custom',
          emojis: customEmojis,
        },
      ]
    : [];

  return (
    <div
      className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
      onClick={onClose}
    >
      <div
        ref={pickerRef}
        onClick={(e) => e.stopPropagation()}
        className="rounded-lg overflow-hidden"
      >
        {allowClear && (
          <div className="bg-gray-800 p-2 border-b border-gray-700">
            <button
              onClick={() => {
                onSelect(null);
                onClose();
              }}
              className="w-full px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded text-sm font-medium"
            >
              Clear Emoji
            </button>
          </div>
        )}
        <Picker
          data={data}
          custom={customCategory}
          onEmojiSelect={handleEmojiSelect}
          theme="dark"
          skinTonePosition="search"
          previewPosition="none"
          navPosition="top"
          perLine={10}
          emojiSize={16}
          emojiButtonSize={24}
          maxFrequentRows={2}
        />
      </div>
    </div>
  );
}
