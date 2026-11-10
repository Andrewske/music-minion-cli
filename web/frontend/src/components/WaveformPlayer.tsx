import { useEffect, useState } from 'react';
import { RefreshCw, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { useQueryClient } from '@tanstack/react-query';
import { refreshWaveform, waveformQueryKey } from '../api/tracks';
import { useActiveAudioElement } from '../contexts/AudioElementContext';
import { usePlayerStore, getCurrentPosition } from '../stores/playerStore';
import { Waveform } from './waveform/Waveform';

const WAVEFORM_HEIGHT = 64;

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
  onTogglePlayPause: () => void;
  onFinish?: () => void;
}

/** Live playback position in seconds while `active`, ticking twice a second. */
function usePositionSeconds(active: boolean): number {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    if (!active) return;
    const tick = (): void => setSeconds(getCurrentPosition(usePlayerStore.getState()) / 1000);
    tick();
    const interval = setInterval(tick, 500);
    return () => clearInterval(interval);
  }, [active]);
  return active ? seconds : 0;
}

/** Fire `onFinish` when the shared audio element ends while this track is current. */
function useTrackEnded(active: boolean, onFinish?: () => void): void {
  const audio = useActiveAudioElement();
  useEffect(() => {
    if (!active || !audio || !onFinish) return;
    audio.addEventListener('ended', onFinish);
    return () => audio.removeEventListener('ended', onFinish);
  }, [active, audio, onFinish]);
}

/** Phone notification metadata and play/pause handlers. */
function useMediaSession(track: WaveformTrack, isPlaying: boolean, onToggle: () => void): void {
  useEffect(() => {
    if (!('mediaSession' in navigator)) return;
    const handlePlay = (): void => { if (!isPlaying) onToggle(); };
    const handlePause = (): void => { if (isPlaying) onToggle(); };
    navigator.mediaSession.setActionHandler('play', handlePlay);
    navigator.mediaSession.setActionHandler('pause', handlePause);
    return () => {
      navigator.mediaSession.setActionHandler('play', null);
      navigator.mediaSession.setActionHandler('pause', null);
    };
  }, [isPlaying, onToggle]);

  useEffect(() => {
    if (!('mediaSession' in navigator)) return;
    if (isPlaying) {
      navigator.mediaSession.metadata = new MediaMetadata({
        title: track.title ?? 'Unknown Title',
        artist: track.artist ?? 'Unknown Artist',
        album: track.album ?? undefined,
      });
    }
    navigator.mediaSession.playbackState = isPlaying ? 'playing' : 'paused';
  }, [isPlaying, track]);
}

/** Re-fetch a track's peaks from source and swap them into the waveform's cache. */
function useRefreshWaveform(trackId: number): { refresh: () => Promise<void>; isRefreshing: boolean } {
  const queryClient = useQueryClient();
  const [isRefreshing, setIsRefreshing] = useState(false);
  const refresh = async (): Promise<void> => {
    setIsRefreshing(true);
    try {
      const data = await refreshWaveform(trackId);
      queryClient.setQueryData(waveformQueryKey(trackId), data);
    } catch {
      toast.error('Failed to refresh waveform — check SoundCloud auth in Settings');
    } finally {
      setIsRefreshing(false);
    }
  };
  return { refresh, isRefreshing };
}

function formatTime(time: number): string {
  const minutes = Math.floor(time / 60);
  const seconds = Math.floor(time % 60);
  return `${minutes}:${seconds.toString().padStart(2, '0')}`;
}

function PlayPauseIcon({ isPlaying }: { isPlaying: boolean }): JSX.Element {
  return isPlaying ? (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4">
      <path fillRule="evenodd" d="M6.75 5.25a.75.75 0 01.75-.75H9a.75.75 0 01.75.75v13.5a.75.75 0 01-.75.75H7.5a.75.75 0 01-.75-.75V5.25zm7.5 0A.75.75 0 0115 4.5h1.5a.75.75 0 01.75.75v13.5a.75.75 0 01-.75.75H15a.75.75 0 01-.75-.75V5.25z" clipRule="evenodd" />
    </svg>
  ) : (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4 ml-0.5">
      <path fillRule="evenodd" d="M4.5 5.653c0-1.426 1.529-2.33 2.779-1.643l11.54 6.348c1.295.712 1.295 2.573 0 3.285L7.28 19.991c-1.25.687-2.779-.217-2.779-1.643V5.653z" clipRule="evenodd" />
    </svg>
  );
}

export function WaveformPlayer({ track, isPlaying, onTogglePlayPause, onFinish }: WaveformPlayerProps): JSX.Element {
  const isCurrent = usePlayerStore((state) => state.currentTrack?.id === track.id);
  const position = usePositionSeconds(isCurrent);
  const { refresh, isRefreshing } = useRefreshWaveform(track.id);
  useTrackEnded(isCurrent, onFinish);
  useMediaSession(track, isPlaying, onTogglePlayPause);
  const duration = track.duration ?? 0;

  return (
    <div className="flex items-center w-full h-full gap-4">
      <button
        onClick={onTogglePlayPause}
        className="w-8 h-8 flex items-center justify-center text-obsidian-accent hover:text-white transition-colors"
        aria-label={isPlaying ? 'Pause' : 'Play'}
      >
        <PlayPauseIcon isPlaying={isPlaying} />
      </button>

      <div className="flex-1 min-w-0">
        <Waveform localTrackId={track.id} durationMs={duration * 1000} height={WAVEFORM_HEIGHT} onActivate={onTogglePlayPause} />
      </div>

      <span className="text-white/30 text-xs font-sf-mono w-20 text-right">
        {formatTime(position)} / {formatTime(duration)}
      </span>

      <button
        onClick={() => void refresh()}
        disabled={isRefreshing}
        className="w-6 h-6 flex items-center justify-center text-white/20 hover:text-white/60 transition-colors disabled:opacity-30"
        aria-label="Refresh waveform"
        title="Refresh waveform"
      >
        {isRefreshing ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
      </button>
    </div>
  );
}
