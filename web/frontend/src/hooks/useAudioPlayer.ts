import { useEffect } from 'react';
import { useComparisonStore } from '../stores/comparisonStore';
import type { TrackInfo } from '../types';

export function useAudioPlayer(track: TrackInfo | null) {
  const { playingTrack, setPlaying } = useComparisonStore();

  useEffect(() => {
    // If this track is playing and another track starts playing, pause this one
    if (playingTrack !== null && playingTrack.id !== track?.id) {
      // The WaveformPlayer component will handle pausing its own instance
      // We just need to update the store state
    }
  }, [playingTrack, track]);

  const playTrack = (trackToPlay: TrackInfo) => {
    setPlaying(trackToPlay);
  };

  const pauseTrack = () => {
    setPlaying(null);
  };

  const isPlaying = playingTrack?.id === track?.id;

  return {
    isPlaying,
    playTrack,
    pauseTrack,
  };
}