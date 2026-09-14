import { useState, type ReactNode } from 'react';
import { Link } from '@tanstack/react-router';
import { AlertCircle, Cloud, EyeOff, Heart, Loader2, Music, ThumbsDown } from 'lucide-react';
import {
  getFeedEventAt,
  getFeedItemBestRank,
  getFeedItemDecision,
  getFeedItemUploader,
  isFeedSyncFailed,
  isFeedSyncPending,
} from '../../api/feed';
import type { FeedArtist, FeedDecision, FeedItem } from '../../api/feed';
import { SoundCloudIcon } from '../icons/SoundCloudIcon';
import { ArtistHoverCard } from './ArtistHoverCard';
import { FeedWaveform } from './FeedWaveform';

function formatFeedRelativeDate(dateStr: string): string {
  const date = new Date(dateStr);
  if (Number.isNaN(date.getTime())) return '-';
  const days = Math.floor((Date.now() - date.getTime()) / 86_400_000);
  if (days < 1) return '<1d';
  if (days < 7) return `${days}d`;
  if (days < 30) return `${Math.floor(days / 7)}w`;
  return `${Math.floor(days / 30)}mo`;
}

function formatDuration(ms: number): string {
  const totalSec = Math.floor(ms / 1000);
  return `${Math.floor(totalSec / 60)}:${String(totalSec % 60).padStart(2, '0')}`;
}

function ArtistName({ artist }: { artist: FeedArtist }): JSX.Element {
  const name = artist.display_name ?? artist.slug;
  if (artist.id === null || artist.id === undefined) return <span>{name}</span>;
  return (
    <ArtistHoverCard artist={artist}>
      <Link
        to="/artists/$artistId"
        params={{ artistId: String(artist.id) }}
        className="underline decoration-dotted decoration-white/20 underline-offset-2 hover:text-white/80"
      >
        {name}
      </Link>
    </ArtistHoverCard>
  );
}

function Attribution({ item }: { item: FeedItem }): JSX.Element {
  const uploader = getFeedItemUploader(item);
  const firstReposter = item.reposters[0];
  const otherReposters = Math.max(0, item.reposter_count - (firstReposter ? 1 : 0));
  const bestRank = getFeedItemBestRank(item);

  return (
    <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-white/50">
      {item.sources.includes('release') && uploader && (
        <span className="truncate">Uploaded by <ArtistName artist={uploader} /></span>
      )}
      {item.sources.includes('repost') && firstReposter && (
        <span className="truncate">
          Reposted by <ArtistName artist={firstReposter} />
          {otherReposters > 0 && ` +${otherReposters} other reposter${otherReposters === 1 ? '' : 's'}`}
        </span>
      )}
      {bestRank !== null && (
        <span className="shrink-0 rounded bg-white/5 px-1.5 py-0.5 font-sf-mono text-[10px] text-white/60">
          #{bestRank}
        </span>
      )}
    </div>
  );
}

function SoundCloudLink({ item }: { item: FeedItem }): JSX.Element | null {
  if (!item.permalink_url) return null;
  return (
    <a
      href={item.permalink_url}
      target="_blank"
      rel="noopener noreferrer"
      aria-label={`Open ${item.title ?? 'track'} on SoundCloud`}
      title="Open on SoundCloud"
      className="flex min-h-10 min-w-10 shrink-0 items-center justify-center rounded p-2 text-white/45 transition-colors hover:bg-white/10 hover:text-[#ff5500] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-obsidian-accent"
    >
      <SoundCloudIcon className="h-4 w-4" />
    </a>
  );
}

function SoundCloudSyncState({ item }: { item: FeedItem }): JSX.Element | null {
  const state = item.action_state;
  const failed = isFeedSyncFailed(state);
  if (!failed && !isFeedSyncPending(state)) return null;
  const label = failed ? 'SoundCloud sync failed' : 'SoundCloud sync pending';
  return (
    <span
      role="status"
      title={state?.error ?? label}
      className={`flex shrink-0 items-center gap-1 text-[11px] ${failed ? 'text-red-400' : 'text-amber-300'}`}
    >
      {failed ? <AlertCircle className="h-3.5 w-3.5" /> : <Loader2 className="h-3.5 w-3.5 animate-spin" />}
      <span className="hidden lg:inline">{label}</span>
    </span>
  );
}

interface FeedTrackCardProps {
  item: FeedItem;
  isPlaying: boolean;
  isUpdating?: boolean;
  onPlay: (item: FeedItem) => void;
  onDecide: (item: FeedItem, decision: FeedDecision) => void;
}

function ActionButton({
  label,
  title,
  active,
  disabled,
  onClick,
  children,
}: {
  label: string;
  title: string;
  active?: boolean;
  disabled?: boolean;
  onClick: () => void;
  children: ReactNode;
}): JSX.Element {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-label={label}
      aria-pressed={active}
      title={title}
      className={`min-h-10 min-w-10 rounded p-2 transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-obsidian-accent disabled:opacity-50 ${
        active ? 'bg-obsidian-accent/15 text-obsidian-accent' : 'text-white/45 hover:bg-white/10 hover:text-white'
      }`}
    >
      {children}
    </button>
  );
}

export function FeedTrackCard({
  item,
  isPlaying,
  isUpdating = false,
  onPlay,
  onDecide,
}: FeedTrackCardProps): JSX.Element {
  const [artworkFailed, setArtworkFailed] = useState(false);
  const decision = getFeedItemDecision(item);
  const hidden = decision === 'hide' || decision === 'nope';
  const playable = item.access !== 'blocked';
  const eventAt = getFeedEventAt(item);

  return (
    <article
      aria-label={`${item.title ?? 'Untitled'} feed item`}
      className={`flex min-h-[84px] items-center gap-3 rounded border px-3 py-2 transition-colors ${
        isPlaying
          ? 'border-obsidian-accent/40 bg-obsidian-accent/10'
          : 'border-obsidian-border bg-obsidian-surface hover:border-white/20'
      } ${hidden ? 'opacity-60' : ''}`}
    >
      <button
        type="button"
        onClick={() => playable && onPlay(item)}
        disabled={!playable}
        aria-label={`Play ${item.title ?? 'track'}`}
        className="shrink-0 rounded focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-obsidian-accent disabled:cursor-not-allowed disabled:opacity-40"
      >
        {item.artwork_url && !artworkFailed ? (
          <img src={item.artwork_url} alt="" width={52} height={52} loading="lazy" onError={() => setArtworkFailed(true)} className="h-[52px] w-[52px] rounded object-cover" />
        ) : (
          <span className="flex h-[52px] w-[52px] items-center justify-center rounded bg-gradient-to-br from-obsidian-accent/20 to-obsidian-surface">
            <Music className="h-5 w-5 text-white/40" />
          </span>
        )}
      </button>

      <div className="min-w-0 flex-1 text-left md:w-64 md:flex-none">
        <button type="button" onClick={() => playable && onPlay(item)} disabled={!playable} className="block w-full rounded text-left focus-visible:outline focus-visible:outline-2 focus-visible:outline-obsidian-accent disabled:cursor-not-allowed">
          <span className={`block truncate text-sm ${isPlaying ? 'text-obsidian-accent' : 'text-white'}`} title={item.title ?? undefined}>
            {item.title ?? 'Untitled'}
            {!playable && <Cloud className="ml-1 inline h-3 w-3 text-white/40" />}
          </span>
        </button>
        <Attribution item={item} />
        <div className="mt-0.5 flex items-center gap-1.5 text-[11px] text-white/35">
          <span title={eventAt ? new Date(eventAt).toLocaleString() : undefined}>{formatFeedRelativeDate(eventAt)}</span>
          {item.genre && <><span>·</span><span className="truncate">{item.genre}</span></>}
        </div>
      </div>

      <div className="hidden min-w-0 flex-1 md:block">
        <FeedWaveform localTrackId={item.local_track_id} durationMs={item.duration_ms} onActivate={() => playable && onPlay(item)} />
      </div>

      <SoundCloudSyncState item={item} />
      <SoundCloudLink item={item} />
      <span className="hidden shrink-0 font-sf-mono text-xs text-white/40 sm:block">{formatDuration(item.duration_ms)}</span>

      <div className="flex shrink-0 items-center gap-0.5" aria-label="Feed decisions">
        <ActionButton label="Nope; hide and count against this recommendation" title="Nope" active={decision === 'nope'} disabled={isUpdating} onClick={() => onDecide(item, 'nope')}>
          <ThumbsDown className="h-4 w-4" />
        </ActionButton>
        <ActionButton label="Hide without affecting recommendations" title="Hide" active={decision === 'hide'} disabled={isUpdating} onClick={() => onDecide(item, 'hide')}>
          <EyeOff className="h-4 w-4" />
        </ActionButton>
        <ActionButton label="Keep; like on SoundCloud and add to monthly playlist" title="Heart" active={decision === 'keep'} disabled={isUpdating || decision === 'keep'} onClick={() => onDecide(item, 'keep')}>
          <Heart className={`h-4 w-4 ${decision === 'keep' ? 'fill-current' : ''}`} />
        </ActionButton>
      </div>
    </article>
  );
}
