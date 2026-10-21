import { useCallback } from 'react';
import { toast } from 'sonner';
import type { Track } from '@music-minion/shared';
import { materializeFeedItems } from '../api/feed';
import { usePlayerStore } from '../stores/playerStore';

/** The fields a reviewed or flagged row needs to be played on its own. */
export interface PlayableFeedRow {
  soundcloud_id: string;
  local_track_id: number | null;
  title: string | null;
  artist_name: string | null;
  duration_ms: number;
}

function rowToTrack(item: PlayableFeedRow, localTrackId: number): Track {
  return {
    id: localTrackId,
    title: item.title ?? 'Untitled',
    artist: item.artist_name ?? 'Unknown artist',
    duration: item.duration_ms / 1000,
  };
}

/** Play one feed row, creating its streaming-only library track first if needed. */
export function usePlayFeedRow(): (item: PlayableFeedRow) => Promise<void> {
  const play = usePlayerStore((state) => state.play);
  return useCallback(
    async (item: PlayableFeedRow): Promise<void> => {
      let localTrackId = item.local_track_id;
      if (localTrackId === null) {
        const created = await materializeFeedItems([item.soundcloud_id]).catch(() => []);
        localTrackId = created[0]?.local_track_id ?? null;
      }
      if (localTrackId === null) {
        toast.error('Could not prepare this SoundCloud track for playback');
        return;
      }
      void play(rowToTrack(item, localTrackId), { type: 'feed', track_ids: [localTrackId] });
    },
    [play]
  );
}
