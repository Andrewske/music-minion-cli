/**
 * Tap-to-play for comparison cards via the global player store.
 * Mirrors web ComparisonView.handleTrackTap: tapping the current track
 * toggles pause/resume; tapping the other track plays it with a
 * 'comparison' context whose queue is just the current pair.
 */
import { useCallback } from 'react';
import type { ComparisonPair, Track, TrackInfo } from '@music-minion/shared';
import { usePlayerStore } from '../stores/playerStore';
import {
  buildComparisonContext,
  getCardPlayState,
  type CardPlayState,
} from '../features/comparison/comparisonState';

interface ComparisonPlayback {
  playStateFor: (trackId: number) => CardPlayState;
  toggle: (track: TrackInfo) => void;
  /** Audio is routed to another connected device, not this phone. */
  playingElsewhere: boolean;
}

const toTrack = (t: TrackInfo): Track => ({
  id: t.id,
  title: t.title,
  artist: t.artist,
  album: t.album,
  duration: t.duration,
});

export function useComparisonPlayback(pair: ComparisonPair): ComparisonPlayback {
  const currentTrackId = usePlayerStore((s) => s.currentTrack?.id ?? null);
  const isPlaying = usePlayerStore((s) => s.isPlaying);
  const playingElsewhere = usePlayerStore((s) => s.activeDeviceId != null && !s.isThisDeviceActive);
  const play = usePlayerStore((s) => s.play);
  const pause = usePlayerStore((s) => s.pause);
  const resume = usePlayerStore((s) => s.resume);

  const playStateFor = useCallback(
    (trackId: number): CardPlayState => getCardPlayState(trackId, currentTrackId, isPlaying),
    [currentTrackId, isPlaying],
  );

  const toggle = useCallback(
    (track: TrackInfo): void => {
      if (currentTrackId !== track.id) {
        void play(toTrack(track), buildComparisonContext(pair));
        return;
      }
      void (isPlaying ? pause() : resume());
    },
    [currentTrackId, isPlaying, pair, play, pause, resume],
  );

  return { playStateFor, toggle, playingElsewhere };
}
