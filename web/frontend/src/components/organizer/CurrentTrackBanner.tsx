import { useCallback, useEffect, useRef, useState } from 'react';
import { usePlayerStore } from '../../stores/playerStore';
import { WaveformPlayer } from '../WaveformPlayer';
import type { Bucket } from '../../api/buckets';
import type { TrackReposter } from '../../types';

function formatTrackDate(dateStr: string | undefined): string | null {
  if (!dateStr) return null;
  const normalized = dateStr.replace(/\//g, '-').replace(' +0000', 'Z').replace(' ', 'T');
  const date = new Date(normalized);
  if (isNaN(date.getTime())) return null;
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const days = Math.floor(diffMs / (1000 * 60 * 60 * 24));
  const full = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  if (days < 1) return `Today • ${full}`;
  if (days < 7) return `${days}d ago • ${full}`;
  if (days < 30) return `${Math.floor(days / 7)}w ago • ${full}`;
  return full;
}

const MAX_VISIBLE_REPOSTERS = 5;

function ReposterLink({ reposter }: { reposter: TrackReposter }): JSX.Element {
  return (
    <a
      href={`https://soundcloud.com/${reposter.slug}`}
      target="_blank"
      rel="noopener noreferrer"
      title={reposter.name}
      className="flex items-center gap-1 hover:opacity-80 transition-opacity"
    >
      <img
        src={reposter.avatar_url?.replace('-large', '-small') ?? ''}
        alt={reposter.name}
        className="w-5 h-5 rounded-full"
      />
      <span className="text-xs text-white/40 truncate">{reposter.name}</span>
    </a>
  );
}

function ReposterList({ reposters }: { reposters: TrackReposter[] }): JSX.Element {
  const [expanded, setExpanded] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const visible = reposters.slice(0, MAX_VISIBLE_REPOSTERS);
  const hiddenCount = reposters.length - visible.length;

  useEffect(() => {
    if (!expanded) return;
    const handleClick = (e: MouseEvent): void => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setExpanded(false);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [expanded]);

  return (
    <div ref={containerRef} className="relative flex items-center gap-2 mt-1.5">
      <span className="text-[10px] uppercase tracking-wider text-white/25">Reposted by</span>
      <div className="flex items-center gap-1.5">
        {visible.map((r) => (
          <ReposterLink key={r.slug} reposter={r} />
        ))}
        {hiddenCount > 0 && (
          <button
            type="button"
            onClick={() => setExpanded((prev) => !prev)}
            className="text-xs text-white/40 hover:text-white/70 px-1.5 py-0.5 rounded bg-white/5 hover:bg-white/10 transition-colors"
          >
            +{hiddenCount} more
          </button>
        )}
      </div>
      {expanded && (
        <div className="absolute top-full left-0 mt-1 z-20 max-h-64 overflow-y-auto bg-obsidian-surface border border-obsidian-border rounded-lg shadow-lg p-2 flex flex-col gap-1.5 min-w-[200px]">
          {reposters.map((r) => (
            <ReposterLink key={r.slug} reposter={r} />
          ))}
        </div>
      )}
    </div>
  );
}

interface CurrentTrackBannerProps {
  buckets: Bucket[];
  trackDate?: string;
  reposters?: TrackReposter[];
}

export function CurrentTrackBanner({ buckets, trackDate, reposters }: CurrentTrackBannerProps): JSX.Element {
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
            {(() => {
              const dateLabel = formatTrackDate(trackDate);
              return dateLabel ? <span className="text-white/30 ml-2">• {dateLabel}</span> : null;
            })()}
          </div>
          {reposters && reposters.length > 0 && <ReposterList reposters={reposters} />}
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

      {/* Keyboard/tap hints */}
      <div className="flex items-center justify-between text-xs">
        {/* Desktop hint */}
        <div className="hidden md:block text-white/40">
          Press <kbd className="px-1.5 py-0.5 bg-white/10 rounded text-white/60">Shift</kbd> +{' '}
          <kbd className="px-1.5 py-0.5 bg-white/10 rounded text-white/60">1</kbd>-<kbd className="px-1.5 py-0.5 bg-white/10 rounded text-white/60">{Math.min(buckets.length, 9)}</kbd> to assign to bucket
        </div>

        {/* Mobile hint */}
        <div className="md:hidden text-white/40">
          Tap bucket below to assign
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
