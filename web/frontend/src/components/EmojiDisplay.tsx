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
 * Custom emojis are identified by type='custom' and have a file_path.
 */
export function EmojiDisplay({
  emojiId,
  emojiData,
  className = '',
  size = 'md',
}: EmojiDisplayProps): JSX.Element {
  const { image: imageSizeClass, text: textSizeClass } = sizeClasses[size];

  // Check if custom emoji via type field
  const isCustom = emojiData?.type === 'custom';

  if (isCustom && emojiData?.file_path) {
    return (
      <img
        src={`/custom_emojis/${emojiData.file_path}`}
        alt={emojiId}
        className={`${imageSizeClass} object-contain ${className}`}
        onError={(e) => {
          // Fallback if image fails to load - hide the broken image
          e.currentTarget.style.display = 'none';
        }}
      />
    );
  }

  // Unicode emoji
  return <span className={`${textSizeClass} ${className}`}>{emojiId}</span>;
}
