import { useState } from 'react';
import type { ReactElement, FormEvent, ChangeEvent } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { X, Music, RefreshCw, Target, Radio, Star, Users } from 'lucide-react';
import { useArtist, useMatchOverride, useDeleteMatchOverride } from '../../hooks/useArtists';
import { ArtistStatChip } from './ArtistStatChip';
import { Button } from '../ui/button';
import type { MatchOverride } from '../../api/artists';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function relativeTime(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const diffS = Math.floor(diffMs / 1000);
  if (diffS < 60) return 'just now';
  const diffM = Math.floor(diffS / 60);
  if (diffM < 60) return `${diffM}m ago`;
  const diffH = Math.floor(diffM / 60);
  if (diffH < 24) return `${diffH}h ago`;
  const diffD = Math.floor(diffH / 24);
  if (diffD < 30) return `${diffD} day${diffD === 1 ? '' : 's'} ago`;
  const diffMo = Math.floor(diffD / 30);
  if (diffMo < 12) return `${diffMo} month${diffMo === 1 ? '' : 's'} ago`;
  const diffY = Math.floor(diffD / 365);
  return `${diffY} year${diffY === 1 ? '' : 's'} ago`;
}

function formatFollowers(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2).replace(/\.?0+$/, '')}m`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1).replace(/\.?0+$/, '')}k`;
  return String(n);
}

// ---------------------------------------------------------------------------
// Section title
// ---------------------------------------------------------------------------

function SectionTitle({ children }: { children: string }): ReactElement {
  return (
    <p className="font-inter text-sm uppercase tracking-wider text-white/50 mb-2">{children}</p>
  );
}

// ---------------------------------------------------------------------------
// Match override row
// ---------------------------------------------------------------------------

interface OverrideRowProps {
  override: MatchOverride;
}

function OverrideRow({ override }: OverrideRowProps): ReactElement {
  const deleteOverride = useDeleteMatchOverride();

  const handleDelete = (): void => {
    deleteOverride.mutate(override.id);
  };

  return (
    <div className="flex items-center justify-between gap-2 py-1">
      <span className="font-sf-mono text-xs text-white/70">
        {override.local_artist_name} <span className="text-white/30">→</span>{' '}
        <span className={override.action === 'merge' ? 'text-emerald-400' : 'text-amber-400'}>
          {override.action}
        </span>
      </span>
      <button
        type="button"
        onClick={handleDelete}
        disabled={deleteOverride.isPending}
        className="text-white/30 hover:text-white/70 transition-colors disabled:opacity-40"
        aria-label="Delete override"
      >
        <X size={12} />
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Add override form
// ---------------------------------------------------------------------------

interface AddOverrideFormProps {
  artistId: number;
}

function AddOverrideForm({ artistId }: AddOverrideFormProps): ReactElement {
  const [localName, setLocalName] = useState('');
  const [action, setAction] = useState<'merge' | 'split'>('merge');
  const createOverride = useMatchOverride();

  const handleSubmit = (e: FormEvent): void => {
    e.preventDefault();
    if (!localName.trim()) return;
    createOverride.mutate(
      { discovery_artist_id: artistId, local_artist_name: localName.trim(), action },
      {
        onSuccess: () => {
          setLocalName('');
          setAction('merge');
        },
      },
    );
  };

  const handleNameChange = (e: ChangeEvent<HTMLInputElement>): void => {
    setLocalName(e.target.value);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-2 mt-3">
      <input
        type="text"
        value={localName}
        onChange={handleNameChange}
        placeholder="Local artist name"
        className="w-full px-3 py-1.5 bg-obsidian-bg border border-obsidian-border text-white placeholder:text-white/30 font-sf-mono text-xs focus:outline-none focus:ring-1 focus:ring-obsidian-accent"
      />
      <div className="flex items-center gap-4">
        <label className="flex items-center gap-1.5 cursor-pointer">
          <input
            type="radio"
            name="override-action"
            value="merge"
            checked={action === 'merge'}
            onChange={() => setAction('merge')}
            className="accent-obsidian-accent"
          />
          <span className="font-sf-mono text-xs text-white/70">Merge</span>
        </label>
        <label className="flex items-center gap-1.5 cursor-pointer">
          <input
            type="radio"
            name="override-action"
            value="split"
            checked={action === 'split'}
            onChange={() => setAction('split')}
            className="accent-obsidian-accent"
          />
          <span className="font-sf-mono text-xs text-white/70">Split</span>
        </label>
        <Button
          type="submit"
          size="sm"
          disabled={!localName.trim() || createOverride.isPending}
          className="ml-auto bg-obsidian-accent hover:bg-obsidian-accent/80 disabled:opacity-50 text-xs h-7 px-3"
        >
          {createOverride.isPending ? 'Adding…' : 'Add'}
        </Button>
      </div>
      <p className="font-sf-mono text-xs text-white/30 leading-relaxed">
        Merge: treat this local artist as same as this SC artist. Split: exclude this local artist from matching.
      </p>
    </form>
  );
}

// ---------------------------------------------------------------------------
// Dialog content (loaded state)
// ---------------------------------------------------------------------------

interface ArtistDetailDialogProps {
  artistId: number | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function DialogBody({ artistId }: { artistId: number }): ReactElement {
  const { data, isLoading, error } = useArtist(artistId);

  if (isLoading) {
    return (
      <div className="py-8 text-center">
        <span className="font-sf-mono text-sm text-white/40">Loading…</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="py-8 text-center">
        <span className="font-sf-mono text-sm text-red-400">{error.message}</span>
      </div>
    );
  }

  if (!data) return <></>;

  const { artist, recent_feed_events, top_library_tracks, match_overrides } = data;

  const hitRateValue = artist.hit_rate !== null
    ? `${Math.round(artist.hit_rate * 100)}%`
    : '—';

  const feedNoiseValue =
    artist.feed_noise_7d === 0 && artist.last_activity_at === null
      ? 'no feed data'
      : `${artist.feed_noise_7d.toFixed(1)}/day (7d)`;

  return (
    <div className="space-y-5">
      {/* 1. Header */}
      <div className="flex items-start gap-4">
        {artist.avatar_url ? (
          <img
            src={artist.avatar_url}
            alt={artist.display_name}
            width={64}
            height={64}
            className="w-16 h-16 object-cover shrink-0"
          />
        ) : (
          <div className="w-16 h-16 shrink-0 flex items-center justify-center bg-obsidian-border text-white/70 font-inter text-2xl font-medium select-none">
            {artist.display_name.charAt(0).toUpperCase()}
          </div>
        )}

        <div className="flex-1 min-w-0">
          <p className="font-inter text-xl font-semibold text-white leading-tight">
            {artist.display_name}
          </p>
          {artist.slug && (
            <p className="font-sf-mono text-sm text-white/50">@{artist.slug}</p>
          )}
          <div className="flex items-center gap-2 mt-1.5 flex-wrap">
            {artist.ranking !== null && (
              <span className="font-sf-mono text-xs text-white/50">#{artist.ranking}</span>
            )}
            {artist.in_top_200 && (
              <span className="font-sf-mono text-xs px-1.5 py-0.5 bg-obsidian-accent/10 text-obsidian-accent border border-obsidian-accent/30">
                Top200
              </span>
            )}
          </div>
        </div>
      </div>

      {/* 2. Quick stats row */}
      <div className="border-t border-obsidian-border pt-4 flex flex-wrap gap-3">
        <ArtistStatChip
          icon={Music}
          label=""
          value={`${artist.library_track_count} tracks`}
          tooltip="tracks in your library from this artist"
        />
        <ArtistStatChip
          icon={RefreshCw}
          label=""
          value={`${artist.repost_in_library_count} reposts`}
          tooltip="reposts from this artist in your library"
        />
        <ArtistStatChip
          icon={Target}
          label="hit"
          value={hitRateValue}
          tooltip="proportion of feed tracks loved"
          accent={artist.hit_rate !== null && artist.hit_rate >= 0.15}
        />
        <ArtistStatChip
          icon={Radio}
          label="feed"
          value={feedNoiseValue}
          tooltip="average tracks per day in feed (last 7 days)"
        />
        {artist.avg_elo !== null && (
          <ArtistStatChip
            icon={Star}
            label="ELO"
            value={Math.round(artist.avg_elo)}
            tooltip="average ELO rating of loved tracks from this artist"
            accent={artist.avg_elo >= 1400}
          />
        )}
        {artist.follower_count !== null && (
          <ArtistStatChip
            icon={Users}
            label=""
            value={`${formatFollowers(artist.follower_count)} followers`}
            tooltip={`${artist.follower_count.toLocaleString()} followers on SoundCloud`}
          />
        )}
      </div>

      {/* 3. Recent feed activity */}
      <div className="border-t border-obsidian-border pt-4">
        <SectionTitle>Recent reposts</SectionTitle>
        {recent_feed_events.length === 0 ? (
          <p className="font-sf-mono text-xs text-white/30">No feed events yet.</p>
        ) : (
          <div className="overflow-y-auto max-h-60 space-y-1 pr-1">
            {recent_feed_events.map((ev) => (
              <p key={ev.track_sc_id} className="font-sf-mono text-xs text-white/60 truncate">
                {ev.track_title} — {ev.track_artist_name}{' '}
                <span className="text-white/30">· {relativeTime(ev.seen_at)}</span>
              </p>
            ))}
          </div>
        )}
      </div>

      {/* 4. Top library tracks */}
      <div className="border-t border-obsidian-border pt-4">
        <SectionTitle>In your library</SectionTitle>
        {top_library_tracks.length === 0 ? (
          <p className="font-sf-mono text-xs text-white/30">
            No tracks in your library by this artist.
          </p>
        ) : (
          <div className="overflow-y-auto max-h-52 space-y-1 pr-1">
            {top_library_tracks.map((track) => (
              <p key={track.id} className="font-sf-mono text-xs text-white/60 truncate">
                {track.title} — {track.artist}
                {track.album && <span className="text-white/30"> · {track.album}</span>}
              </p>
            ))}
          </div>
        )}
      </div>

      {/* 5. Match overrides */}
      <div className="border-t border-obsidian-border pt-4">
        <SectionTitle>Artist match overrides</SectionTitle>
        {match_overrides.length === 0 ? (
          <p className="font-sf-mono text-xs text-white/30">No overrides yet.</p>
        ) : (
          <div className="space-y-0.5">
            {match_overrides.map((ov) => (
              <OverrideRow key={ov.id} override={ov} />
            ))}
          </div>
        )}
        <AddOverrideForm artistId={artistId} />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Dialog shell
// ---------------------------------------------------------------------------

export function ArtistDetailDialog({
  artistId,
  open,
  onOpenChange,
}: ArtistDetailDialogProps): ReactElement {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0" />
        <Dialog.Content className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-50 w-full max-w-2xl max-h-[85vh] overflow-y-auto bg-obsidian-surface border border-obsidian-border p-6 space-y-5 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0">
          {/* Dialog title (visually hidden, required for a11y) */}
          <Dialog.Title className="sr-only">Artist details</Dialog.Title>

          {/* Close button */}
          <Dialog.Close asChild>
            <button
              type="button"
              className="absolute top-4 right-4 text-white/40 hover:text-white/80 transition-colors focus:outline-none focus:ring-1 focus:ring-obsidian-accent"
              aria-label="Close"
            >
              <X size={18} />
            </button>
          </Dialog.Close>

          {open && artistId !== null ? (
            <DialogBody artistId={artistId} />
          ) : null}

          {/* Footer */}
          <div className="border-t border-obsidian-border pt-4 flex justify-end">
            <Dialog.Close asChild>
              <Button variant="ghost" className="text-white/60 hover:text-white">
                Close
              </Button>
            </Dialog.Close>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
