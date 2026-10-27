import { findCustomEmojiSrc, useCustomEmojis } from '../hooks/useCustomEmojis';

interface EmojiDisplayProps {
  emojiId: string;
  emojiData?: { type: string; file_path?: string | null };
  className?: string;
  size?: 'sm' | 'md' | 'lg';
}

const sizeClasses = {
  sm: { image: 'w-4 h-4', text: 'text-base' },
  md: { image: 'w-8 h-8', text: 'text-3xl' },
  lg: { image: 'w-12 h-12', text: 'text-5xl' },
};

/**
 * Renders either a Unicode emoji or a custom emoji image.
 * Custom emojis come from emojiData (type='custom' + file_path) or, failing
 * that, are looked up by UUID in the custom emoji list.
 */
export function EmojiDisplay({
  emojiId,
  emojiData,
  className = '',
  size = 'md',
}: EmojiDisplayProps): JSX.Element {
  const { image: imageSizeClass, text: textSizeClass } = sizeClasses[size];

  const customEmojis = useCustomEmojis();
  // Callers without emojiData (e.g. bucket emoji_id) get the image via the shared custom list
  const src = emojiData?.type === 'custom' && emojiData.file_path
    ? `/custom_emojis/${emojiData.file_path}`
    : findCustomEmojiSrc(customEmojis, emojiId);

  if (src) {
    return (
      <img
        src={src}
        alt={emojiId}
        className={`${imageSizeClass} object-contain ${className}`}
        onError={(e) => {
          e.currentTarget.style.display = 'none';
        }}
      />
    );
  }

  // Unicode emoji
  return <span className={`${textSizeClass} ${className}`}>{emojiId}</span>;
}
