import { useEffect } from 'react';
import { useComparisonStore } from '../stores/comparisonStore';

export function useAudioPlayer(trackId: number | null) {
  const { playingTrackId, setPlaying } = useComparisonStore();

  useEffect(() => {
    // If this track is playing and another track starts playing, pause this one
    if (playingTrackId !== null && playingTrackId !== trackId) {
      // The WaveformPlayer component will handle pausing its own instance
      // We just need to update the store state
    }
  }, [playingTrackId, trackId]);

  const playTrack = (id: number) => {
    setPlaying(id);
  };

  const pauseTrack = () => {
    setPlaying(null);
  };

  const isPlaying = playingTrackId === trackId;

  return {
    isPlaying,
    playTrack,
    pauseTrack,
  };
}