import { useState } from 'react';
import { EmojiReactions } from './EmojiReactions';
import { EmojiPicker } from './EmojiPicker';
import { useTrackEmojis } from '../hooks/useTrackEmojis';

interface EmojiTrackActionsProps {
  track: { id: number; emojis?: string[] };
  onUpdate: (updatedTrack: { id: number; emojis?: string[] }) => void;
  compact?: boolean;
  className?: string;
}

/**
 * Self-contained emoji management for any track.
 * Handles state, API calls, optimistic updates, and error handling.
 *
 * Usage:
 *   <EmojiTrackActions track={track} onUpdate={setTrack} />
 */
export function EmojiTrackActions({
  track,
  onUpdate,
  compact = false,
  className = ''
}: EmojiTrackActionsProps): JSX.Element {
  const [showPicker, setShowPicker] = useState(false);

  const { addEmoji, removeEmoji, isAdding } = useTrackEmojis(track, onUpdate);

  const handleAddEmoji = async (emoji: string): Promise<void> => {
    await addEmoji(emoji);
    setShowPicker(false);
  };

  const emojisArray = track.emojis || [];

  return (
    <>
      <EmojiReactions
        trackId={track.id}
        emojis={emojisArray}
        onRemove={removeEmoji}
        onAddClick={() => setShowPicker(true)}
        compact={compact}
        className={className}
        isAdding={isAdding}
      />

      {showPicker && (
        <EmojiPicker
          onSelect={handleAddEmoji}
          onClose={() => setShowPicker(false)}
        />
      )}
    </>
  );
}
