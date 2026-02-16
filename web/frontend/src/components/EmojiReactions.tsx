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
              relative group ${compact ? 'text-sm' : 'text-base'}
              leading-none hover:opacity-70 disabled:opacity-30 transition-opacity
            `}
            aria-label={`Remove emoji`}
          >
            <EmojiDisplay
              emojiId={emojiId}
              emojiData={metadata}
              size={compact ? 'sm' : 'md'}
            />
            <span className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
              <span className="text-obsidian-accent text-xs font-bold">×</span>
            </span>
          </button>
        );
      })}

      {/* Add button (hidden in compact mode) */}
      {!compact && (
        <button
          onClick={onAddClick}
          disabled={isAdding}
          className={`text-sm font-bold transition-colors ${
            isAdding
              ? 'text-green-500 opacity-30 cursor-not-allowed'
              : 'text-green-500 hover:text-green-400'
          }`}
          aria-label="Add emoji"
        >
          +
        </button>
      )}
    </div>
  );
}
