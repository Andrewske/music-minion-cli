import { useEffect, useRef, useState } from 'react';
import { ExternalLink, Heart, Music } from 'lucide-react';
import { EmojiTrackActions } from '../EmojiTrackActions';
import type { TrackReposter } from '../../types';
import { GenrePicker } from './GenrePicker';
import { formatKey } from './keyNotation';
import { parseTrackDate } from './trackDate';

function formatTrackDate(dateStr: string | undefined): string | null {
  const date = parseTrackDate(dateStr);
  if (!date) return null;
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
function scArtwork(url: string, size: 't200x200' | 't500x500'): string {
  return url.replace('-large.', `-${size}.`);
}

/**
 * Stored SoundCloud artwork when present, else the endpoint that pulls art embedded
 * in the local file. Returns undefined once the image fails so callers show a placeholder.
 */
function useArtworkSrc(
  trackId: number,
  artworkUrl: string | undefined,
  size: 't200x200' | 't500x500',
): { src: string | undefined; onError: () => void } {
  const src = artworkUrl ? scArtwork(artworkUrl, size) : `/api/tracks/${trackId}/artwork`;
  // Keyed by src so a new track retries instead of inheriting the last failure
  const [failedSrc, setFailedSrc] = useState<string>();
  return { src: failedSrc === src ? undefined : src, onError: () => setFailedSrc(src) };
}

/** Deterministic hue from the title so artless tracks still get a moody wash. */
function titleHue(title: string): number {
  let h = 0;
  for (let i = 0; i < title.length; i++) h = (h * 31 + title.charCodeAt(i)) % 360;
  return h;
}

const MAX_VISIBLE_REPOSTERS = 5;

interface TrackMetaRowProps {
  trackId: number;
  bpm?: number;
  keySignature?: string;
  genre?: string | null;
  onGenreChange: (genre: string | null) => void;
}

/** BPM and key are read-only (Serato owns them); genre is editable. */
function TrackMetaRow({ trackId, bpm, keySignature, genre, onGenreChange }: TrackMetaRowProps): JSX.Element {
  return (
    <div className="mt-1.5 flex items-center gap-3 text-xs text-white/50">
      <span title="BPM">
        {bpm ? Math.round(bpm) : '–'} <span className="text-white/30">BPM</span>
      </span>
      <span title="Key">
        <span className="text-white/30">Key</span> {formatKey(keySignature)}
      </span>
      {/* Keyed so an open picker resets when the track changes */}
      <GenrePicker key={trackId} trackId={trackId} genre={genre} onChange={onGenreChange} />
    </div>
  );
}

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
          liked ? 'text-red-500 fill-current' : 'text-white/25'
        }`}
      />
    </span>
  );
}

interface ArtworkProps {
  trackId: number;
  artworkUrl?: string;
  title: string;
}

export function Backdrop({ trackId, artworkUrl, title }: ArtworkProps): JSX.Element {
  const hue = titleHue(title);
  const { src, onError } = useArtworkSrc(trackId, artworkUrl, 't500x500');
  if (!src) {
    return (
      <div
        aria-hidden
        className="absolute inset-0 rounded-lg pointer-events-none"
        style={{
          background: `linear-gradient(120deg, hsl(${hue} 45% 13%), hsl(${(hue + 50) % 360} 40% 7%))`,
        }}
      />
    );
  }
  // Clipped here rather than on the card so dropdowns can overflow the card
  return (
    <div aria-hidden className="absolute inset-0 overflow-hidden rounded-lg pointer-events-none">
      <img
        src={src}
        alt=""
        aria-hidden
        onError={onError}
        className="absolute inset-0 w-full h-full object-cover scale-125 blur-2xl saturate-150 opacity-30 pointer-events-none"
      />
      <div
        aria-hidden
        className="absolute inset-0 pointer-events-none bg-linear-to-b/srgb from-black/50 via-black/60 to-black/80"
      />
    </div>
  );
}

function ArtThumbnail({ trackId, artworkUrl, title }: ArtworkProps): JSX.Element {
  const { src, onError } = useArtworkSrc(trackId, artworkUrl, 't200x200');
  if (!src) {
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
      src={src}
      alt={title}
      onError={onError}
      className="w-16 h-16 shrink-0 rounded-md object-cover ring-1 ring-white/10 shadow-lg"
    />
  );
}

export interface TrackBannerInfoProps {
  trackId: number;
  title: string;
  artist?: string;
  artworkUrl?: string;
  trackDate?: string;
  reposters?: TrackReposter[];
  scLiked?: boolean;
  soundcloudUrl?: string;
  bpm?: number;
  keySignature?: string;
  genre?: string | null;
  onGenreChange: (genre: string | null) => void;
  emojis?: string[];
  onEmojisChange: (emojis: string[]) => void;
  /** Rendered at the end of the title row (e.g. a menu button). */
  titleAccessory?: JSX.Element;
}

/** Artwork, title, links, BPM/key/genre, emojis and reposters for one track. */
export function TrackBannerInfo({
  trackId,
  title,
  artist,
  artworkUrl,
  trackDate,
  reposters,
  scLiked,
  soundcloudUrl,
  bpm,
  keySignature,
  genre,
  onGenreChange,
  emojis,
  onEmojisChange,
  titleAccessory,
}: TrackBannerInfoProps): JSX.Element {
  const dateLabel = formatTrackDate(trackDate);
  return (
    <div className="flex items-start gap-3">
      <ArtThumbnail trackId={trackId} artworkUrl={artworkUrl} title={title} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-medium text-white/95 truncate drop-shadow-xs">{title}</span>
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
          {titleAccessory && <div className="ml-auto shrink-0">{titleAccessory}</div>}
        </div>
        <div className="text-sm text-white/60 truncate">
          {artist ?? 'Unknown Artist'}
          {dateLabel && <span className="text-white/35 ml-2">• {dateLabel}</span>}
        </div>
        <TrackMetaRow
          trackId={trackId}
          bpm={bpm}
          keySignature={keySignature}
          genre={genre}
          onGenreChange={onGenreChange}
        />
        {/* Keyed so an open emoji picker closes when the track changes */}
        <EmojiTrackActions
          key={trackId}
          track={{ id: trackId, emojis }}
          onUpdate={(updated) => onEmojisChange(updated.emojis ?? [])}
          className="mt-2"
        />
        {reposters && reposters.length > 0 && <ReposterStack reposters={reposters} />}
      </div>
    </div>
  );
}
