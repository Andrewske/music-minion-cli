import { useCallback, useState } from 'react';
import { toast } from 'sonner';
import { addEmojiToTrack, removeEmojiFromTrack } from '../api/emojis';

interface TrackWithEmojis {
  id: number;
  emojis?: string[];
}

export interface UseTrackEmojisReturn {
  addEmoji: (emoji: string) => Promise<void>;
  removeEmoji: (emoji: string) => Promise<void>;
  isAdding: boolean;
  isRemoving: boolean;
}

/**
 * Hook for managing track emojis with optimistic updates and error handling.
 * Works with any component that has track data with emojis field.
 *
 * @param track - Current track object
 * @param updateTrack - Function to update track in parent state
 */
export function useTrackEmojis<T extends TrackWithEmojis>(
  track: T | null,
  updateTrack: (updated: T) => void
): UseTrackEmojisReturn {
  const [isAdding, setIsAdding] = useState(false);
  const [isRemoving, setIsRemoving] = useState(false);

  const addEmoji = useCallback(
    async (emoji: string): Promise<void> => {
      if (!track || isAdding) return;

      const previousEmojis = track.emojis || [];

      setIsAdding(true);

      // Optimistic update
      updateTrack({
        ...track,
        emojis: [...previousEmojis, emoji],
      });

      try {
        const result = await addEmojiToTrack(track.id, emoji);
        if (!result.added) {
          // Emoji already existed, revert
          updateTrack({ ...track, emojis: previousEmojis });
        }
      } catch (err) {
        // Rollback on error
        updateTrack({ ...track, emojis: previousEmojis });
        toast.error('Failed to add emoji');
        console.error('Add emoji error:', err);
      } finally {
        setIsAdding(false);
      }
    },
    [track, updateTrack, isAdding]
  );

  const removeEmoji = useCallback(
    async (emoji: string): Promise<void> => {
      if (!track || isRemoving) return;

      const previousEmojis = track.emojis || [];

      setIsRemoving(true);

      // Optimistic update
      updateTrack({
        ...track,
        emojis: previousEmojis.filter((e) => e !== emoji),
      });

      try {
        await removeEmojiFromTrack(track.id, emoji);
      } catch (err) {
        // Rollback on error
        updateTrack({ ...track, emojis: previousEmojis });
        toast.error('Failed to remove emoji');
        console.error('Remove emoji error:', err);
      } finally {
        setIsRemoving(false);
      }
    },
    [track, updateTrack, isRemoving]
  );

  return { addEmoji, removeEmoji, isAdding, isRemoving };
}
