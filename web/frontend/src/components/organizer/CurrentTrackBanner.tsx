import { useCallback } from 'react';
import { usePlayerStore } from '../../stores/playerStore';
import { WaveformPlayer } from '../WaveformPlayer';
import type { Bucket } from '../../api/buckets';

interface CurrentTrackBannerProps {
  buckets: Bucket[];
}

export function CurrentTrackBanner({ buckets }: CurrentTrackBannerProps): JSX.Element {
  const currentTrack = usePlayerStore((s) => s.currentTrack);
  const isPlaying = usePlayerStore((s) => s.isPlaying);
  const pause = usePlayerStore((s) => s.pause);
  const resume = usePlayerStore((s) => s.resume);

  const handleTogglePlayPause = useCallback((): void => {
    if (isPlaying) {
      pause();
    } else {
      resume();
    }
  }, [isPlaying, pause, resume]);

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
      </div>

      {/* Waveform player */}
      <div className="h-16 mb-3">
        <WaveformPlayer
          track={currentTrack}
          isPlaying={isPlaying}
          onTogglePlayPause={handleTogglePlayPause}
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
