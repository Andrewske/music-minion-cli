import { useState, useEffect, useRef, useCallback } from 'react';
import { useRadioStore } from '../stores/radioStore';

function formatDuration(seconds: number | null): string {
  if (seconds === null || seconds === undefined) return '--:--';
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return mins + ':' + secs.toString().padStart(2, '0');
}

function formatPosition(ms: number): string {
  // Clamp negative values (can occur from clock drift or timezone issues)
  if (ms < 0) ms = 0;
  const totalSeconds = Math.floor(ms / 1000);
  const mins = Math.floor(totalSeconds / 60);
  const secs = totalSeconds % 60;
  return mins + ':' + secs.toString().padStart(2, '0');
}

export function RadioPlayer(): JSX.Element {
  const { isMuted, nowPlaying, isLoading, error, toggleMute } = useRadioStore();
  const [localPosition, setLocalPosition] = useState<number>(0);
  const lastFetchTime = useRef<number>(Date.now());

  // Sync local position when we get fresh data from server
  useEffect(() => {
    if (nowPlaying) {
      setLocalPosition(nowPlaying.position_ms);
      lastFetchTime.current = Date.now();
    }
  }, [nowPlaying]);

  // Increment local position between polls for smooth progress bar
  useEffect(() => {
    const interval = setInterval(() => {
      setLocalPosition((prev) => {
        const elapsed = Date.now() - lastFetchTime.current;
        if (nowPlaying) {
          return nowPlaying.position_ms + elapsed;
        }
        return prev + 250;
      });
    }, 250);

    return () => clearInterval(interval);
  }, [nowPlaying]);

  const handleMuteToggle = useCallback(() => {
    toggleMute();
  }, [toggleMute]);

  if (isLoading) {
    return (
      <div className="bg-slate-900 rounded-lg p-6 animate-pulse">
        <div className="flex items-center gap-4">
          <div className="w-16 h-16 bg-slate-800 rounded-lg" />
          <div className="flex-1 space-y-2">
            <div className="h-6 bg-slate-800 rounded w-48" />
            <div className="h-4 bg-slate-800 rounded w-32" />
          </div>
        </div>
        <div className="mt-4 h-2 bg-slate-800 rounded" />
      </div>
    );
  }

  if (error || !nowPlaying) {
    return (
      <div className="bg-slate-900 rounded-lg p-6">
        <div className="text-center text-slate-400">
          <p className="text-lg font-medium">No station active</p>
          <p className="text-sm mt-1">Activate a station to start listening</p>
        </div>
      </div>
    );
  }

  const track = nowPlaying.track;
  const durationMs = (track.duration ?? 0) * 1000;
  const progressPercent = durationMs > 0 ? Math.max(0, Math.min(100, (localPosition / durationMs) * 100)) : 0;

  return (
    <div className="bg-slate-900 rounded-lg p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <span className="text-xs font-semibold text-emerald-500 uppercase tracking-wider">
          Now Playing
        </span>
        <span className="text-xs text-slate-500 bg-slate-800 px-2 py-1 rounded">
          {nowPlaying.station_name}
        </span>
      </div>

      {/* Track Info */}
      <div className="flex items-center gap-4">
        {/* Mute/Unmute Button */}
        <button
          onClick={handleMuteToggle}
          className="w-16 h-16 bg-gradient-to-br from-emerald-600 to-emerald-800 rounded-lg flex items-center justify-center shrink-0 hover:from-emerald-500 hover:to-emerald-700 transition-all"
          aria-label={isMuted ? 'Unmute' : 'Mute'}
        >
          {isMuted ? (
            <svg className="w-8 h-8 text-white" fill="currentColor" viewBox="0 0 24 24">
              <path d="M16.5 12c0-1.77-1.02-3.29-2.5-4.03v2.21l2.45 2.45c.03-.2.05-.41.05-.63zm2.5 0c0 .94-.2 1.82-.54 2.64l1.51 1.51C20.63 14.91 21 13.5 21 12c0-4.28-2.99-7.86-7-8.77v2.06c2.89.86 5 3.54 5 6.71zM4.27 3L3 4.27 7.73 9H3v6h4l5 5v-6.73l4.25 4.25c-.67.52-1.42.93-2.25 1.18v2.06c1.38-.31 2.63-.95 3.69-1.81L19.73 21 21 19.73l-9-9L4.27 3zM12 4L9.91 6.09 12 8.18V4z"/>
            </svg>
          ) : (
            <svg className="w-8 h-8 text-white" fill="currentColor" viewBox="0 0 24 24">
              <path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z"/>
            </svg>
          )}
        </button>

        {/* Track Details */}
        <div className="flex-1 min-w-0">
          <h2 className="text-lg font-semibold text-white truncate">
            {track.title ?? 'Unknown Title'}
          </h2>
          <p className="text-slate-400 truncate">
            {track.artist ?? 'Unknown Artist'}
          </p>
        </div>
      </div>

      {/* Progress Bar */}
      <div className="mt-4">
        <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
          <div
            className="h-full bg-emerald-500 transition-all duration-200"
            style={{ width: progressPercent + '%' }}
          />
        </div>
        <div className="flex justify-between mt-1 text-xs text-slate-500">
          <span>{formatPosition(localPosition)}</span>
          <span>{formatDuration(track.duration)}</span>
        </div>
      </div>

    </div>
  );
}
