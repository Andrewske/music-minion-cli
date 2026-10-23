/**
 * Tap-to-play for comparison cards via the global player store.
 * Mirrors web ComparisonView.handleTrackTap: tapping the current track
 * toggles pause/resume; tapping the other track plays it with a
 * 'comparison' context whose queue is just the current pair.
 * When a vote loads the next pair while an old-pair track is playing,
 * track A of the new pair starts automatically.
 */
import { useCallback, useEffect, useRef } from 'react';
import type { ComparisonPair, Track, TrackInfo } from '@music-minion/shared';
import { usePlayerStore } from '../stores/playerStore';
import {
  buildComparisonContext,
  getCardPlayState,
  shouldAutoPlayNextPair,
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

/** Auto-play new track A when the pair changes mid-playback of the old pair. */
function useAutoPlayOnPairChange(pair: ComparisonPair): void {
  const prevPairRef = useRef<ComparisonPair>(pair);

  useEffect(() => {
    const prevPair = prevPairRef.current;
    prevPairRef.current = pair;
    if (prevPair === pair) return;
    const { currentTrack, isPlaying, play } = usePlayerStore.getState();
    if (!shouldAutoPlayNextPair(prevPair, pair, currentTrack?.id, isPlaying)) return;
    void play(toTrack(pair.track_a), buildComparisonContext(pair));
  }, [pair]);
}

export function useComparisonPlayback(pair: ComparisonPair): ComparisonPlayback {
  const currentTrackId = usePlayerStore((s) => s.currentTrack?.id ?? null);
  const isPlaying = usePlayerStore((s) => s.isPlaying);
  const playingElsewhere = usePlayerStore((s) => s.activeDeviceId != null && !s.isThisDeviceActive);
  const play = usePlayerStore((s) => s.play);
  const pause = usePlayerStore((s) => s.pause);
  const resume = usePlayerStore((s) => s.resume);
  useAutoPlayOnPairChange(pair);

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
