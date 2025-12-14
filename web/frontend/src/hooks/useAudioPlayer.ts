import { useCallback } from 'react';
import { useComparisonStore } from '../stores/comparisonStore';
import type { TrackInfo } from '../types';

export function useAudioPlayer(track: TrackInfo | null) {
  const { currentTrack, isPlaying, setIsPlaying, selectAndPlay } = useComparisonStore();

  const playTrack = useCallback((trackToPlay: TrackInfo) => {
    selectAndPlay(trackToPlay);
  }, [selectAndPlay]);

  const pauseTrack = useCallback(() => {
    setIsPlaying(false);
  }, [setIsPlaying]);

  const isTrackPlaying = isPlaying && currentTrack?.id === track?.id;

  return {
    isPlaying: isTrackPlaying,
    playTrack,
    pauseTrack,
  };
}