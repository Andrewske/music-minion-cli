import { useQuery } from '@tanstack/react-query';
import type { EmojiInfo } from '../api/emojis';
import { EmojiDisplay } from './EmojiDisplay';

interface EmojiReactionsProps {
  trackId: number;
  emojis: string[];
  onRemove: (emoji: string) => void;
  onAddClick: () => void;
  compact?: boolean;  // For tables/mini-displays - smaller badges, no "+ Add" button
  className?: string; // Allow parent to control layout
  isAdding?: boolean;  // Disable "+ Add" while adding
  isRemoving?: boolean;  // Visual feedback while removing
}

/**
 * Check if emoji_id is a UUID (custom emoji pattern).
 */
function isUuidPattern(emojiId: string): boolean {
  return emojiId.length === 36 && emojiId.split('-').length === 5;
}

/**
 * Fetch metadata for custom emojis (UUID patterns).
 */
async function fetchCustomEmojiMetadata(emojiIds: string[]): Promise<Record<string, EmojiInfo>> {
  const uuids = emojiIds.filter(isUuidPattern);
  if (uuids.length === 0) return {};

  // Fetch all emojis and filter to custom ones we need
  const res = await fetch('/api/emojis/all?limit=200');
  if (!res.ok) return {};

  const allEmojis: EmojiInfo[] = await res.json();
  const customMap: Record<string, EmojiInfo> = {};

  for (const emoji of allEmojis) {
    if (emoji.type === 'custom' && uuids.includes(emoji.emoji_id)) {
      customMap[emoji.emoji_id] = emoji;
    }
  }

  return customMap;
}

export function EmojiReactions({
  emojis,
  onRemove,
  onAddClick,
  compact = false,
  className = '',
  isAdding = false,
}: EmojiReactionsProps): JSX.Element {
  // Fetch custom emoji metadata if any UUIDs are present
  const hasCustomEmojis = emojis.some(isUuidPattern);
  const { data: customMetadata = {} } = useQuery({
    queryKey: ['custom-emoji-metadata', emojis.filter(isUuidPattern)],
    queryFn: () => fetchCustomEmojiMetadata(emojis),
    enabled: hasCustomEmojis,
    staleTime: 5 * 60 * 1000, // Cache for 5 minutes
  });

  return (
    <div className={`flex flex-wrap gap-2 items-center ${className}`}>
      {/* Emoji badges */}
      {emojis.map((emojiId) => {
        const isCustom = isUuidPattern(emojiId);
        const metadata = isCustom ? customMetadata[emojiId] : undefined;

        return (
          <button
            key={emojiId}
            onClick={() => onRemove(emojiId)}
            className={`
              ${compact ? 'px-1.5 py-0.5' : 'px-2 py-1'}
              bg-slate-800 hover:bg-red-600 rounded-md transition-colors flex items-center justify-center
            `}
            aria-label={`Remove emoji`}
          >
            <EmojiDisplay
              emojiId={emojiId}
              emojiData={metadata}
              size={compact ? 'sm' : 'md'}
            />
          </button>
        );
      })}

      {/* Add button (hidden in compact mode) */}
      {!compact && (
        <button
          onClick={onAddClick}
          disabled={isAdding}
          className={`px-3 py-1 rounded-md text-sm font-medium text-white transition-colors ${
            isAdding
              ? 'bg-emerald-700 opacity-50 cursor-not-allowed'
              : 'bg-emerald-600 hover:bg-emerald-500'
          }`}
          aria-label="Add emoji"
        >
          {isAdding ? 'Adding...' : '+ Add'}
        </button>
      )}
    </div>
  );
}
