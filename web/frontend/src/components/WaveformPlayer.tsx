import { useEffect, useCallback } from 'react';
import { useWavesurfer } from '../hooks/useWavesurfer';
import { useAudioElement } from '../contexts/AudioElementContext';
import { usePlayerStore } from '../stores/playerStore';

/** Minimal track interface - both Track and TrackInfo satisfy this */
interface WaveformTrack {
  id: number;
  title: string;
  artist?: string;
  album?: string;
  duration?: number;
}

interface WaveformPlayerProps {
  track: WaveformTrack;
  isPlaying: boolean;
  onTogglePlayPause?: () => void;
  onFinish?: () => void;
}

export function WaveformPlayer({ track, isPlaying, onTogglePlayPause, onFinish }: WaveformPlayerProps) {
  const sharedAudio = useAudioElement();
  const globalTrackId = usePlayerStore(state => state.currentTrack?.id);
  const { seek } = usePlayerStore();

  // Only use shared audio if this track is the global current track
  const audioElement = track.id === globalTrackId ? sharedAudio : null;

  // When using external audio, route waveform seeks through the store
  // This ensures WebSocket sync to other devices
  const handleSeekViaStore = useCallback((progress: number) => {
    if (!track.duration) return;
    const positionMs = progress * track.duration * 1000;
    seek(positionMs);
  }, [seek, track.duration]);

  const { containerRef, currentTime, duration, error, retryLoad, togglePlayPause } = useWavesurfer({
    trackId: track.id,
    isPlaying,
    onFinish,
    externalAudio: audioElement,
    trackDuration: track.duration,
    onSeek: audioElement ? handleSeekViaStore : undefined,  // Route through store when external
  });

  // Update Media Session for phone notifications
  const updateMediaSession = useCallback(() => {
    if (!('mediaSession' in navigator)) return;

    navigator.mediaSession.metadata = new MediaMetadata({
      title: track.title ?? 'Unknown Title',
      artist: track.artist ?? 'Unknown Artist',
      album: track.album ?? undefined,
    });
    navigator.mediaSession.playbackState = 'playing';
  }, [track]);

  // Set up Media Session action handlers
  useEffect(() => {
    if (!('mediaSession' in navigator)) return;

    const handlePlay = () => {
      if (onTogglePlayPause && !isPlaying) {
        onTogglePlayPause();
      } else if (!isPlaying) {
        togglePlayPause();
      }
    };

    const handlePause = () => {
      if (onTogglePlayPause && isPlaying) {
        onTogglePlayPause();
      } else if (isPlaying) {
        togglePlayPause();
      }
    };

    navigator.mediaSession.setActionHandler('play', handlePlay);
    navigator.mediaSession.setActionHandler('pause', handlePause);

    return () => {
      navigator.mediaSession.setActionHandler('play', null);
      navigator.mediaSession.setActionHandler('pause', null);
    };
  }, [isPlaying, onTogglePlayPause, togglePlayPause]);

  // Update metadata when track changes or playback starts
  useEffect(() => {
    if (isPlaying) {
      updateMediaSession();
    } else if ('mediaSession' in navigator) {
      navigator.mediaSession.playbackState = 'paused';
    }
  }, [isPlaying, updateMediaSession]);

  const formatTime = (time: number) => {
    const minutes = Math.floor(time / 60);
    const seconds = Math.floor(time % 60);
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
  };

  return (
    <div className="flex items-center w-full h-full gap-4">
      {/* Play/Pause Button */}
      <button
        onClick={onTogglePlayPause || togglePlayPause}
        className="w-8 h-8 flex items-center justify-center text-obsidian-accent hover:text-white transition-colors"
        aria-label={isPlaying ? 'Pause' : 'Play'}
      >
        {isPlaying ? (
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4">
            <path fillRule="evenodd" d="M6.75 5.25a.75.75 0 01.75-.75H9a.75.75 0 01.75.75v13.5a.75.75 0 01-.75.75H7.5a.75.75 0 01-.75-.75V5.25zm7.5 0A.75.75 0 0115 4.5h1.5a.75.75 0 01.75.75v13.5a.75.75 0 01-.75.75H15a.75.75 0 01-.75-.75V5.25z" clipRule="evenodd" />
          </svg>
        ) : (
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4 ml-0.5">
            <path fillRule="evenodd" d="M4.5 5.653c0-1.426 1.529-2.33 2.779-1.643l11.54 6.348c1.295.712 1.295 2.573 0 3.285L7.28 19.991c-1.25.687-2.779-.217-2.779-1.643V5.653z" clipRule="evenodd" />
          </svg>
        )}
      </button>

      {/* Waveform container */}
      <div className="flex-1 h-full relative">
        {/* Error UI */}
        {error && (
          <div role="alert" aria-live="polite" className="absolute inset-0 z-20 bg-rose-950/90 flex flex-col items-center justify-center p-2 rounded-r-lg">
            <p className="text-rose-200 text-xs mb-1 text-center truncate w-full px-2">{error}</p>
            <button
              onClick={retryLoad}
              className="text-rose-400 underline text-xs hover:text-rose-300"
            >
              Retry
            </button>
          </div>
        )}

        {/* Waveform visualization */}
        <div ref={containerRef} className="w-full h-full" />
      </div>

      {/* Time display */}
      <span className="text-white/30 text-xs font-sf-mono w-20 text-right">
        {formatTime(currentTime)} / {formatTime(duration)}
      </span>
    </div>
  );
}
