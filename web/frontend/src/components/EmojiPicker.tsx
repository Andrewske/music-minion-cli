import * as Dialog from '@radix-ui/react-dialog';
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
 * Rendered as a Radix dialog so it stacks above (and takes focus from) any
 * parent Radix dialog; backdrop click and Escape close it.
 */
export function EmojiPicker({ onSelect, onClose, allowClear = false }: EmojiPickerProps): JSX.Element {
  // Fetch custom emojis from backend in emoji-mart format
  const { data: customEmojis } = useQuery({
    queryKey: ['emojis', 'custom-for-picker'],
    queryFn: async () => {
      const res = await fetch('/api/emojis/custom-picker');
      if (!res.ok) return [];
      return res.json();
    },
  });

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
    <Dialog.Root open onOpenChange={(isOpen) => !isOpen && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-60 bg-black/50" />
        <Dialog.Content
          aria-describedby={undefined}
          className="fixed left-1/2 top-1/2 z-60 -translate-x-1/2 -translate-y-1/2 rounded-lg overflow-hidden"
        >
          <Dialog.Title className="sr-only">Choose emoji</Dialog.Title>
            {allowClear && (
              <div className="bg-gray-800 p-2 border-b border-gray-700">
                <button
                  onClick={() => {
                    onSelect(null);
                    onClose();
                  }}
                  className="w-full px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-sm text-sm font-medium"
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
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
