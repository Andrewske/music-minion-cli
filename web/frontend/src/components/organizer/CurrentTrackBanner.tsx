import { useState, useEffect, useRef } from 'react';
import { usePlayerStore, getCurrentPosition } from '../../stores/playerStore';
import { Slider } from '../ui/slider';
import type { Bucket } from '../../api/buckets';

interface CurrentTrackBannerProps {
  buckets: Bucket[];
}

export function CurrentTrackBanner({ buckets }: CurrentTrackBannerProps): JSX.Element {
  const currentTrack = usePlayerStore((s) => s.currentTrack);
  const isPlaying = usePlayerStore((s) => s.isPlaying);

  // Progress calculation
  const [progress, setProgress] = useState(0);
  const progressIntervalRef = useRef<number | null>(null);

  useEffect(() => {
    // Clear existing interval
    if (progressIntervalRef.current) {
      clearInterval(progressIntervalRef.current);
      progressIntervalRef.current = null;
    }

    // Reset progress if no track or not playing
    if (!currentTrack?.duration || !isPlaying) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setProgress(0);
      return;
    }

    const duration = currentTrack.duration;
    const updateProgress = (): void => {
      const pos = getCurrentPosition(usePlayerStore.getState());
      setProgress((pos / (duration * 1000)) * 100);
    };

    updateProgress();
    progressIntervalRef.current = setInterval(updateProgress, 250);

    return () => {
      if (progressIntervalRef.current) {
        clearInterval(progressIntervalRef.current);
        progressIntervalRef.current = null;
      }
    };
  }, [currentTrack?.duration, isPlaying]);

  // Format duration as mm:ss
  const formatDuration = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  // Current position in seconds
  const currentSeconds = currentTrack?.duration
    ? (progress / 100) * currentTrack.duration
    : 0;

  if (!currentTrack) {
    return (
      <div className="bg-obsidian-surface border border-obsidian-border rounded-lg p-4 mb-4">
        <div className="text-white/50 text-sm text-center">
          No track playing. Click a track below to start.
        </div>
      </div>
    );
  }

  return (
    <div className="bg-obsidian-surface border border-obsidian-border rounded-lg p-4 mb-4">
      {/* Track info */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex-1 min-w-0">
          <div className="font-medium text-white/90 truncate">
            {currentTrack.title}
          </div>
          <div className="text-sm text-white/60 truncate">
            {currentTrack.artist ?? 'Unknown Artist'}
          </div>
        </div>

        {/* Duration display */}
        <div className="text-xs text-white/40 font-sf-mono ml-4">
          {formatDuration(currentSeconds)} / {formatDuration(currentTrack.duration ?? 0)}
        </div>
      </div>

      {/* Progress bar */}
      <div className="mb-3">
        <Slider
          value={[progress]}
          max={100}
          className="w-full"
        />
      </div>

      {/* Keyboard hints */}
      <div className="flex items-center justify-between text-xs">
        <div className="text-white/40">
          Press <kbd className="px-1.5 py-0.5 bg-white/10 rounded text-white/60">Shift</kbd> +{' '}
          <kbd className="px-1.5 py-0.5 bg-white/10 rounded text-white/60">1</kbd>-<kbd className="px-1.5 py-0.5 bg-white/10 rounded text-white/60">{Math.min(buckets.length, 9)}</kbd> to assign to bucket
        </div>

        {buckets.length === 0 && (
          <div className="text-amber-400/80">
            Create buckets first to assign tracks
          </div>
        )}
      </div>
    </div>
  );
}
