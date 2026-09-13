import { useCallback, useEffect, useRef, useState } from 'react';
import { ExternalLink, Heart, Music } from 'lucide-react';
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

/** SoundCloud CDN stores artwork as `-large.` (100px); swap for a bigger crop. */
function scArtwork(url: string | undefined, size: 't200x200' | 't500x500'): string | undefined {
  return url?.replace('-large.', `-${size}.`);
}

/** Deterministic hue from the title so artless tracks still get a moody wash. */
function titleHue(title: string): number {
  let h = 0;
  for (let i = 0; i < title.length; i++) h = (h * 31 + title.charCodeAt(i)) % 360;
  return h;
}

const MAX_VISIBLE_REPOSTERS = 5;

function ReposterLink({ reposter }: { reposter: TrackReposter }): JSX.Element {
  return (
    <a
      href={`https://soundcloud.com/${reposter.slug}`}
      target="_blank"
      rel="noopener noreferrer"
      title={reposter.name}
      className="flex items-center gap-1.5 hover:opacity-80 transition-opacity"
    >
      <img
        src={reposter.avatar_url?.replace('-large', '-small') ?? ''}
        alt={reposter.name}
        className="w-5 h-5 rounded-full"
      />
      <span className="text-xs text-white/50 truncate">{reposter.name}</span>
    </a>
  );
}

function ReposterStack({ reposters }: { reposters: TrackReposter[] }): JSX.Element {
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
    <div ref={containerRef} className="relative mt-2 flex items-center gap-2">
      <span className="text-[10px] uppercase tracking-wider text-white/30">Reposted by</span>
      <button
        type="button"
        onClick={() => setExpanded((prev) => !prev)}
        title={visible.map((r) => r.name).join(', ')}
        className="flex items-center hover:opacity-90 transition-opacity"
      >
        <span className="flex -space-x-1.5">
          {visible.map((r) => (
            <img
              key={r.slug}
              src={r.avatar_url?.replace('-large', '-small') ?? ''}
              alt={r.name}
              className="w-6 h-6 rounded-full ring-2 ring-black/60"
            />
          ))}
        </span>
        {hiddenCount > 0 && (
          <span className="ml-2 text-xs text-white/50 px-1.5 py-0.5 rounded-full bg-white/10">
            +{hiddenCount}
          </span>
        )}
      </button>
      <span className="hidden sm:block text-xs text-white/40 truncate max-w-[200px]">
        {visible[0]?.name}
        {visible.length > 1 && ` and ${reposters.length - 1} more`}
      </span>
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

function ScHeart({ liked }: { liked: boolean }): JSX.Element {
  return (
    <span
      title={liked ? 'Liked on SoundCloud' : 'Not saved on SoundCloud'}
      className="shrink-0 inline-flex"
    >
      <Heart
        className={`w-4 h-4 ${
          liked ? 'text-orange-500 fill-orange-500 drop-shadow-[0_0_6px_rgba(255,85,0,0.5)]' : 'text-white/25'
        }`}
      />
    </span>
  );
}

function Backdrop({ artworkUrl, title }: { artworkUrl?: string; title: string }): JSX.Element {
  const hue = titleHue(title);
  if (!artworkUrl) {
    return (
      <div
        aria-hidden
        className="absolute inset-0 pointer-events-none"
        style={{
          background: `linear-gradient(120deg, hsl(${hue} 45% 13%), hsl(${(hue + 50) % 360} 40% 7%))`,
        }}
      />
    );
  }
  return (
    <>
      <img
        src={scArtwork(artworkUrl, 't500x500')}
        alt=""
        aria-hidden
        className="absolute inset-0 w-full h-full object-cover scale-125 blur-2xl saturate-150 opacity-30 pointer-events-none"
      />
      <div
        aria-hidden
        className="absolute inset-0 pointer-events-none bg-gradient-to-b from-black/50 via-black/60 to-black/80"
      />
    </>
  );
}

function ArtThumbnail({ artworkUrl, title }: { artworkUrl?: string; title: string }): JSX.Element {
  if (!artworkUrl) {
    const hue = titleHue(title);
    return (
      <div
        className="w-16 h-16 shrink-0 rounded-md ring-1 ring-white/10 shadow-lg flex items-center justify-center"
        style={{ background: `hsl(${hue} 35% 18%)` }}
      >
        <Music className="w-6 h-6 text-white/30" />
      </div>
    );
  }
  return (
    <img
      src={scArtwork(artworkUrl, 't200x200')}
      alt={title}
      className="w-16 h-16 shrink-0 rounded-md object-cover ring-1 ring-white/10 shadow-lg"
    />
  );
}

interface CurrentTrackBannerProps {
  buckets: Bucket[];
  trackDate?: string;
  reposters?: TrackReposter[];
  artworkUrl?: string;
  scLiked?: boolean;
  soundcloudUrl?: string;
}

export function CurrentTrackBanner({
  buckets,
  trackDate,
  reposters,
  artworkUrl,
  scLiked,
  soundcloudUrl,
}: CurrentTrackBannerProps): JSX.Element {
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

  const dateLabel = formatTrackDate(trackDate);

  return (
    <div className="relative overflow-hidden bg-obsidian-surface border border-obsidian-border rounded-lg mb-4">
      <Backdrop artworkUrl={artworkUrl} title={currentTrack.title} />

      <div className="relative p-4">
        {/* Track info */}
        <div className="flex items-start gap-3 mb-3">
          <ArtThumbnail artworkUrl={artworkUrl} title={currentTrack.title} />
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="font-medium text-white/95 truncate drop-shadow-sm">
                {currentTrack.title}
              </span>
              <ScHeart liked={scLiked ?? false} />
              {soundcloudUrl && (
                <a
                  href={soundcloudUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  title="Open on SoundCloud"
                  className="shrink-0 inline-flex text-white/40 hover:text-orange-500 transition-colors"
                >
                  <ExternalLink className="w-4 h-4" />
                </a>
              )}
            </div>
            <div className="text-sm text-white/60 truncate">
              {currentTrack.artist ?? 'Unknown Artist'}
              {dateLabel && <span className="text-white/35 ml-2">• {dateLabel}</span>}
            </div>
            {reposters && reposters.length > 0 && <ReposterStack reposters={reposters} />}
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
    </div>
  );
}
