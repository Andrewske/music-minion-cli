import { useEffect, useCallback } from 'react';
import { useComparisonStore } from '../stores/comparisonStore';
import type { TrackInfo } from '../types';

export function useAudioPlayer(track: TrackInfo | null, isComparisonMode = false) {
  const { playingTrack, setPlaying } = useComparisonStore();

  useEffect(() => {
    // If this track is playing and another track starts playing, pause this one
    // But skip this in comparison mode to allow seamless switching
    if (!isComparisonMode && playingTrack !== null && playingTrack.id !== track?.id) {
      // The WaveformPlayer component will handle pausing its own instance
      // We just need to update the store state
    }
  }, [playingTrack, track, isComparisonMode]);

  const playTrack = useCallback((trackToPlay: TrackInfo) => {
    setPlaying(trackToPlay);
  }, [setPlaying]);

  const pauseTrack = useCallback(() => {
    setPlaying(null);
  }, [setPlaying]);

  const isPlaying = playingTrack?.id === track?.id;

  return {
    isPlaying,
    playTrack,
    pauseTrack,
  };
}