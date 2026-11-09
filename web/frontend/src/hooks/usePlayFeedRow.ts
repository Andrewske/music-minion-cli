import { useCallback } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { cacheMaterializedReviewed } from '../components/feed/reviewed';
import { resolveLocalTrackId, rowToTrack, type PlayableFeedRow } from '../lib/feedPlayback';
import { usePlayerStore } from '../stores/playerStore';

export type { PlayableFeedRow };

/** Play one feed row, creating its streaming-only library track first if needed. */
export function usePlayFeedRow(): (item: PlayableFeedRow) => Promise<void> {
  const play = usePlayerStore((state) => state.play);
  const queryClient = useQueryClient();
  return useCallback(
    async (item: PlayableFeedRow): Promise<void> => {
      const localTrackId = await resolveLocalTrackId(item);
      if (localTrackId === null) {
        toast.error('Could not prepare this SoundCloud track for playback');
        return;
      }
      if (item.local_track_id === null) cacheMaterializedReviewed(queryClient, item.soundcloud_id, localTrackId);
      void play(rowToTrack(item, localTrackId), { type: 'feed', track_ids: [localTrackId] });
    },
    [play, queryClient]
  );
}
