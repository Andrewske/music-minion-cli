import { useState } from 'react';
import type { ReactElement, ReactNode } from 'react';
import * as HoverCard from '@radix-ui/react-hover-card';
import { useQueryClient } from '@tanstack/react-query';
import {
  Heart,
  ListMusic,
  Loader2,
  Music,
  RefreshCw,
  Star,
  Target,
  UserMinus,
  Users,
} from 'lucide-react';
import { toast } from 'sonner';
import type { FeedArtist } from '../../api/feed';
import type { ArtistStats } from '../../api/artists';
import { useArtist, useUnfollowArtist } from '../../hooks/useArtists';
import { ArtistStatChip } from '../artists/ArtistStatChip';
import { ConfirmUnfollowDialog } from '../artists/ConfirmUnfollowDialog';

function formatFollowers(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2).replace(/\.?0+$/, '')}m`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1).replace(/\.?0+$/, '')}k`;
  return String(n);
}

function relativeTime(iso: string): string {
  const diffD = Math.floor((Date.now() - new Date(iso).getTime()) / (1000 * 60 * 60 * 24));
  if (diffD < 1) return 'today';
  if (diffD < 30) return `${diffD}d ago`;
  if (diffD < 365) return `${Math.floor(diffD / 30)}mo ago`;
  return `${Math.floor(diffD / 365)}y ago`;
}

const ACTIVITY_DOT: Record<ArtistStats['activity_state'], string> = {
  active: 'bg-emerald-500',
  silent: 'bg-amber-500',
  dormant: 'bg-slate-600',
};

interface ArtistHoverCardProps {
  artist: FeedArtist;
  children: ReactNode;
}

export function ArtistHoverCard({ artist, children }: ArtistHoverCardProps): ReactElement {
  const [hoverOpen, setHoverOpen] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const queryClient = useQueryClient();

  // Lazy fetch — only when the card is actually open
  const { data: detail, isLoading } = useArtist(hoverOpen ? artist.id : null);
  const unfollowMutation = useUnfollowArtist();

  const stats = detail?.artist ?? null;
  const topTracks = detail?.top_library_tracks.slice(0, 3) ?? [];

  const handleUnfollow = (): void => {
    unfollowMutation.mutate(artist.id, {
      onSuccess: () => {
        setConfirmOpen(false);
        setHoverOpen(false);
        void queryClient.invalidateQueries({ queryKey: ['feed'] });
        toast.success(`Unfollowed ${artist.display_name ?? artist.slug}`);
      },
      onError: (err) => toast.error(`Unfollow failed: ${err.message}`),
    });
  };

  return (
    <>
      <HoverCard.Root
        openDelay={350}
        closeDelay={150}
        open={hoverOpen || confirmOpen}
        onOpenChange={setHoverOpen}
      >
        <HoverCard.Trigger asChild>{children}</HoverCard.Trigger>
        <HoverCard.Portal>
          <HoverCard.Content
            side="bottom"
            align="start"
            sideOffset={6}
            collisionPadding={8}
            className="z-50 w-72 rounded bg-obsidian-surface border border-obsidian-border shadow-xl shadow-black/50 data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95"
          >
            {/* Header — renders instantly from feed data */}
            <header className="flex items-center gap-3 px-4 py-3">
              {artist.avatar_url ? (
                <img
                  src={artist.avatar_url}
                  alt=""
                  width={40}
                  height={40}
                  className="w-10 h-10 rounded-full object-cover shrink-0"
                />
              ) : (
                <div className="w-10 h-10 rounded-full shrink-0 flex items-center justify-center bg-obsidian-border text-white/70 font-inter font-medium select-none">
                  {(artist.display_name ?? artist.slug).charAt(0).toUpperCase()}
                </div>
              )}
              <div className="flex-1 min-w-0">
                <div className="font-inter font-medium text-sm text-white/90 truncate">
                  {artist.display_name ?? artist.slug}
                </div>
                <div className="font-sf-mono text-xs text-white/50 truncate">@{artist.slug}</div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                {stats?.ranking != null && (
                  <span className="font-sf-mono text-xs text-white/50">#{stats.ranking}</span>
                )}
                {artist.in_top_200 && (
                  <span className="font-sf-mono text-xs px-1.5 py-0.5 bg-obsidian-accent/10 text-obsidian-accent border border-obsidian-accent/30">
                    Top200
                  </span>
                )}
                {stats && (
                  <span
                    className={`w-2 h-2 rounded-full ${ACTIVITY_DOT[stats.activity_state]}`}
                    title={
                      stats.last_activity_at
                        ? `last active ${relativeTime(stats.last_activity_at)}`
                        : 'no activity'
                    }
                  />
                )}
              </div>
            </header>

            {/* Stats */}
            <div className="border-t border-obsidian-border px-4 py-3">
              {isLoading || !stats ? (
                <div className="flex justify-center py-2 text-white/40">
                  <Loader2 className="w-4 h-4 animate-spin" />
                </div>
              ) : (
                <div className="space-y-1.5">
                  <div className="flex flex-wrap gap-3">
                    <ArtistStatChip
                      icon={Heart}
                      label=""
                      value={`${stats.sc_liked_count} liked`}
                      tooltip="tracks by this artist in your SoundCloud likes"
                      accent={stats.sc_liked_count > 0}
                    />
                    <ArtistStatChip
                      icon={ListMusic}
                      label=""
                      value={`${stats.playlist_track_count} in playlists`}
                      tooltip="tracks by this artist in your playlists"
                      accent={stats.playlist_track_count > 0}
                    />
                  </div>
                  <div className="flex flex-wrap gap-3">
                    <ArtistStatChip
                      icon={Music}
                      label=""
                      value={`${stats.library_track_count} in library`}
                      tooltip="all tracks by this artist in your library (local + SoundCloud)"
                    />
                    <ArtistStatChip
                      icon={RefreshCw}
                      label=""
                      value={`${stats.repost_in_library_count} reposts`}
                      tooltip="reposts from this artist in your library"
                    />
                  </div>
                  <div className="flex flex-wrap gap-3">
                    <ArtistStatChip
                      icon={Target}
                      label="hit"
                      value={stats.hit_rate !== null ? `${Math.round(stats.hit_rate * 100)}%` : '—'}
                      tooltip="proportion of feed tracks loved"
                      accent={stats.hit_rate !== null && stats.hit_rate >= 0.15}
                    />
                    {stats.avg_elo !== null && (
                      <ArtistStatChip
                        icon={Star}
                        label="ELO"
                        value={Math.round(stats.avg_elo)}
                        tooltip="average ELO of loved tracks"
                        accent={stats.avg_elo >= 1400}
                      />
                    )}
                    {stats.follower_count !== null && (
                      <ArtistStatChip
                        icon={Users}
                        label=""
                        value={formatFollowers(stats.follower_count)}
                        tooltip={`${stats.follower_count.toLocaleString()} followers on SoundCloud`}
                      />
                    )}
                  </div>
                  {stats.last_loved_at !== null && (
                    <div className="flex items-center gap-1 font-sf-mono text-xs text-white/50">
                      <Heart size={12} className="shrink-0" />
                      <span>last loved {relativeTime(stats.last_loved_at)}</span>
                    </div>
                  )}
                  {topTracks.length > 0 && (
                    <div className="pt-1.5 space-y-0.5">
                      <div className="font-sf-mono text-[10px] uppercase tracking-wider text-white/30">
                        Top in library
                      </div>
                      {topTracks.map((t) => (
                        <div
                          key={t.id}
                          className="flex items-baseline gap-2 font-sf-mono text-xs text-white/60"
                        >
                          <span className="truncate">{t.title}</span>
                          <span className="ml-auto shrink-0 text-white/30">{t.play_count}×</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Footer */}
            <footer className="border-t border-obsidian-border px-4 py-2">
              {stats && !stats.is_following ? (
                <span className="font-sf-mono text-xs text-white/40">Not following</span>
              ) : (
                <button
                  onClick={() => setConfirmOpen(true)}
                  disabled={!stats || unfollowMutation.isPending}
                  className="w-full flex items-center justify-center gap-1.5 py-1.5 rounded text-xs text-white/50 hover:text-red-400 hover:bg-red-400/10 border border-transparent hover:border-red-400/30 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  <UserMinus size={13} />
                  Unfollow
                </button>
              )}
            </footer>
          </HoverCard.Content>
        </HoverCard.Portal>
      </HoverCard.Root>

      <ConfirmUnfollowDialog
        artist={stats}
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        onConfirm={handleUnfollow}
        isPending={unfollowMutation.isPending}
      />
    </>
  );
}
