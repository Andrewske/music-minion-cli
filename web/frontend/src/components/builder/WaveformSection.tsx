import type { Track } from '../../api/builder';
import { WaveformPlayer } from '../WaveformPlayer';

interface WaveformSectionProps {
  track: Track;
  isPlaying: boolean;
  loopEnabled: boolean;
  onTogglePlayPause: () => void;
  onLoopChange: (enabled: boolean) => void;
  onFinish: () => void;
}

/**
 * Waveform player wrapper with loop toggle for playlist builders.
 * Consistent height (h-16) with centered loop checkbox below.
 */
export function WaveformSection({
  track,
  isPlaying,
  loopEnabled,
  onTogglePlayPause,
  onLoopChange,
  onFinish,
}: WaveformSectionProps): JSX.Element {
  return (
    <>
      {/* Waveform */}
      <div className="h-16 border-t border-b border-obsidian-border">
        <WaveformPlayer
          track={{
            id: track.id,
            title: track.title,
            artist: track.artist,
            rating: track.elo_rating || 0,
            comparison_count: 0,
            wins: 0,
            losses: 0,
            has_waveform: true,
          }}
          isPlaying={isPlaying}
          onTogglePlayPause={onTogglePlayPause}
          onFinish={onFinish}
        />
      </div>

      {/* Loop toggle */}
      <div className="flex justify-center">
        <label className="flex items-center gap-3 text-white/30 text-sm cursor-pointer hover:text-white/50 transition-colors">
          <input
            type="checkbox"
            checked={loopEnabled}
            onChange={(e) => onLoopChange(e.target.checked)}
            className="w-3 h-3 accent-obsidian-accent"
          />
          Loop
        </label>
      </div>
    </>
  );
}
