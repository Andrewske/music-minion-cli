import { useState } from 'react';
import { ChevronLeft, ChevronRight, Music, Pause, Play, Repeat2, Upload } from 'lucide-react';
import type { StoriesArtist, StoriesTrack } from '../../api/stories';
import { getScLikeState } from '../../api/feed';
import { SoundCloudIcon } from '../icons/SoundCloudIcon';
import { ScLikeHeart } from '../ScLikeHeart';
import { ArtistAvatar } from './StoriesArtistList';
import { ACTIVITY_LABELS, formatTimeAgo, largeArtwork, soundCloudUrl } from './storiesFormat';

/** SoundCloud-style segment bar: one dash per track, heard ones filled. */
function TrackSegments({ tracks, focusId }: { tracks: readonly StoriesTrack[]; focusId: string }): JSX.Element {
  return (
    <div className="flex gap-1" aria-hidden="true">
      {tracks.map((track) => (
        <span
          key={track.soundcloud_id}
          className={`h-0.5 flex-1 rounded-full ${
            track.soundcloud_id === focusId ? 'bg-obsidian-accent' : track.listened ? 'bg-white/70' : 'bg-white/20'
          }`}
        />
      ))}
    </div>
  );
}

function SoundCloudLink({ track }: { track: StoriesTrack }): JSX.Element {
  return (
    <a
      href={soundCloudUrl(track)}
      target="_blank"
      rel="noopener noreferrer"
      aria-label={`Open ${track.title ?? 'track'} on SoundCloud`}
      title="Open on SoundCloud"
      className="flex min-h-10 min-w-10 shrink-0 items-center justify-center rounded-sm p-2 text-white/45 transition-colors hover:bg-white/10 hover:text-[#ff5500] focus-visible:outline-solid focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-obsidian-accent"
    >
      <SoundCloudIcon className="h-5 w-5" />
    </a>
  );
}

function ArtistHeader({ artist, track }: { artist: StoriesArtist; track: StoriesTrack }): JSX.Element {
  const KindIcon = track.kind === 'repost' ? Repeat2 : Upload;
  return (
    <div className="flex items-center gap-3">
      <ArtistAvatar artist={artist} size={40} />
      <div className="min-w-0">
        <p className="truncate text-sm font-semibold text-white">{artist.display_name ?? artist.slug}</p>
        <p className="flex items-center gap-1 text-xs text-white/50">
          <KindIcon className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
          <span className="truncate">
            {ACTIVITY_LABELS[track.kind]} · {formatTimeAgo(track.activity_at)}
          </span>
        </p>
      </div>
      <span className="ml-auto flex items-center">
        <ScLikeHeart state={getScLikeState(track.sc_liked, track.sc_like_action)} className="h-5 w-5" />
        <SoundCloudLink track={track} />
      </span>
    </div>
  );
}

/** Previous / Next with no verdict: plain navigation through the stories. */
export interface StoriesNav {
  canGoPrevious: boolean;
  canGoNext: boolean;
  onPrevious: () => void;
  onNext: () => void;
}

interface NavArrowProps {
  side: 'left' | 'right';
  disabled: boolean;
  onClick: () => void;
}

function NavArrow({ side, disabled, onClick }: NavArrowProps): JSX.Element {
  const Icon = side === 'left' ? ChevronLeft : ChevronRight;
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-label={side === 'left' ? 'Previous track' : 'Next track'}
      title={side === 'left' ? 'Previous' : 'Next'}
      className={`absolute top-1/2 z-10 flex h-11 w-11 -translate-y-1/2 items-center justify-center rounded-full bg-black/55 text-white shadow-lg backdrop-blur-sm transition-colors hover:bg-black/75 focus-visible:outline-solid focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-obsidian-accent disabled:pointer-events-none disabled:opacity-0 ${
        side === 'left' ? 'left-2' : 'right-2'
      }`}
    >
      <Icon className="h-6 w-6" />
    </button>
  );
}

interface ArtworkProps {
  track: StoriesTrack;
  isPlaying: boolean;
  onTogglePlay: () => void;
  nav: StoriesNav;
}

function Artwork({ track, isPlaying, onTogglePlay, nav }: ArtworkProps): JSX.Element {
  const [failedUrl, setFailedUrl] = useState<string | null>(null);
  const src = largeArtwork(track.artwork_url);
  const title = track.title ?? 'Untitled';
  return (
    <div className="group relative aspect-square w-full overflow-hidden rounded bg-obsidian-surface">
      {src && failedUrl !== src ? (
        <img src={src} alt="" onError={() => setFailedUrl(src)} className="h-full w-full object-cover" />
      ) : (
        <span className="flex h-full w-full items-center justify-center bg-linear-to-br/srgb from-obsidian-accent/20 to-obsidian-surface">
          <Music className="h-16 w-16 text-white/30" />
        </span>
      )}
      <button
        type="button"
        onClick={onTogglePlay}
        aria-label={isPlaying ? `Pause ${title}` : `Play ${title}`}
        className="absolute inset-0 flex items-center justify-center bg-black/0 transition-colors hover:bg-black/25 focus-visible:outline-solid focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-obsidian-accent"
      >
        <span
          className={`flex h-20 w-20 items-center justify-center rounded-full bg-black/60 text-white shadow-lg backdrop-blur-sm transition-opacity ${
            isPlaying ? 'opacity-0 group-hover:opacity-100 group-focus-within:opacity-100' : 'opacity-100'
          }`}
        >
          {isPlaying ? <Pause className="h-9 w-9 fill-current" /> : <Play className="ml-1 h-9 w-9 fill-current" />}
        </span>
      </button>
      <NavArrow side="left" disabled={!nav.canGoPrevious} onClick={nav.onPrevious} />
      <NavArrow side="right" disabled={!nav.canGoNext} onClick={nav.onNext} />
      <div className="pointer-events-none absolute bottom-3 left-3 right-3 flex flex-col items-start gap-0.5">
        <span className="max-w-full truncate bg-black/85 px-2 py-1 text-sm font-semibold text-white sm:text-base">{title}</span>
        <span className="max-w-full truncate bg-black/85 px-2 py-0.5 text-sm text-white/55">{track.artist_name ?? 'Unknown artist'}</span>
      </div>
    </div>
  );
}

interface StoriesHeroProps {
  artist: StoriesArtist;
  track: StoriesTrack;
  isPlaying: boolean;
  onTogglePlay: () => void;
  nav: StoriesNav;
}

/** Segment bar, "<artist> reposted a track · 18 hours ago", and the big artwork with Previous / Next arrows. */
export function StoriesHero({ artist, track, isPlaying, onTogglePlay, nav }: StoriesHeroProps): JSX.Element {
  return (
    <section aria-label={`${artist.display_name ?? artist.slug} story`} className="flex flex-col gap-3">
      <TrackSegments tracks={artist.tracks} focusId={track.soundcloud_id} />
      <ArtistHeader artist={artist} track={track} />
      <Artwork track={track} isPlaying={isPlaying} onTogglePlay={onTogglePlay} nav={nav} />
    </section>
  );
}
