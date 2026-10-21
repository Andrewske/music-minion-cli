import { useCallback, useEffect, useRef } from 'react';
import {
  INITIAL_LISTEN_STATE,
  listenStatsFor,
  recordListenSample,
  type ListenSample,
  type ListenState,
  type ListenStats,
} from '../lib/feedListen';
import { getCurrentPosition, usePlayerStore, type PlayerStore } from '../stores/playerStore';

const SAMPLE_INTERVAL_MS = 1_000;

function sampleOf(state: PlayerStore): ListenSample {
  return {
    trackId: state.currentTrack?.id ?? null,
    isPlaying: state.isPlaying,
    positionMs: getCurrentPosition(state),
    at: Date.now(),
  };
}

/**
 * Tracks how long each track plays while the feed is open. Samples on a
 * timer and on every play/pause/track change, so transitions are exact.
 */
export function useFeedListenTracker(): (localTrackId: number | null) => ListenStats {
  const stateRef = useRef<ListenState>(INITIAL_LISTEN_STATE);

  useEffect(() => {
    const sample = (): void => {
      stateRef.current = recordListenSample(stateRef.current, sampleOf(usePlayerStore.getState()));
    };
    sample();
    const timer = window.setInterval(sample, SAMPLE_INTERVAL_MS);
    const unsubscribe = usePlayerStore.subscribe((next, previous) => {
      if (next.isPlaying !== previous.isPlaying || next.currentTrack?.id !== previous.currentTrack?.id) {
        // Close the previous state's interval before recording the new one.
        stateRef.current = recordListenSample(stateRef.current, sampleOf(previous));
        sample();
      }
    });
    return () => {
      window.clearInterval(timer);
      unsubscribe();
    };
  }, []);

  return useCallback((localTrackId: number | null): ListenStats => {
    stateRef.current = recordListenSample(stateRef.current, sampleOf(usePlayerStore.getState()));
    return listenStatsFor(stateRef.current, localTrackId);
  }, []);
}
