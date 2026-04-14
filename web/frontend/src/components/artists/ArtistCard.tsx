import type { ReactElement } from 'react';
import {
  Music,
  RefreshCw,
  Target,
  Radio,
  Star,
  Users,
  MoreHorizontal,
} from 'lucide-react';
import type { ArtistStats } from '../../api/artists';
import { Button } from '../ui/button';
import { ArtistStatChip } from './ArtistStatChip';
import type { ChipKey } from './ArtistStatChip';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatFollowers(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2).replace(/\.?0+$/, '')}m`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1).replace(/\.?0+$/, '')}k`;
  return String(n);
}

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

const ACTIVITY_DOT: Record<ArtistStats['activity_state'], string> = {
  active: 'bg-emerald-500',
  silent: 'bg-amber-500',
  dormant: 'bg-slate-600',
};

const ALL_CHIPS = new Set<ChipKey>([
  'library', 'reposts', 'hit_rate', 'first_loved', 'feed_noise', 'activity', 'elo', 'followers',
]);

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

interface AvatarProps {
  avatarUrl: string | null;
  displayName: string;
}

function Avatar({ avatarUrl, displayName }: AvatarProps): ReactElement {
  if (avatarUrl) {
    return (
      <img
        src={avatarUrl}
        alt={displayName}
        width={48}
        height={48}
        className="w-12 h-12 object-cover shrink-0"
      />
    );
  }
  return (
    <div className="w-12 h-12 shrink-0 flex items-center justify-center bg-obsidian-border text-white/70 font-inter text-lg font-medium select-none">
      {displayName.charAt(0).toUpperCase()}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

interface ArtistCardProps {
  artist: ArtistStats;
  visibleChips?: Set<ChipKey>;
  onUnfollow?: (id: number) => void;
  onDetails?: (id: number) => void;
  isUnfollowing?: boolean;
}

export function ArtistCard({
  artist,
  visibleChips = ALL_CHIPS,
  onUnfollow,
  onDetails,
  isUnfollowing = false,
}: ArtistCardProps): ReactElement {
  const show = (key: ChipKey): boolean => visibleChips.has(key);

  const activityTooltip = artist.last_activity_at
    ? `last active ${relativeTime(artist.last_activity_at)}`
    : 'no activity';

  const hitRateValue = artist.hit_rate !== null
    ? `${Math.round(artist.hit_rate * 100)}%`
    : '—';

  const feedNoiseValue =
    artist.feed_noise_7d === 0 && artist.last_activity_at === null
      ? 'no feed data'
      : `${artist.feed_noise_7d.toFixed(1)}/day (7d)`;

  const firstLovedText = artist.first_loved_track !== null
    ? `♥ first loved "${artist.first_loved_track.title}" · ${relativeTime(artist.first_loved_track.loved_at)}`
    : null;

  const handleUnfollow = (): void => {
    if (artist.id !== null) onUnfollow?.(artist.id);
  };

  const handleDetails = (): void => {
    if (artist.id !== null) onDetails?.(artist.id);
  };

  return (
    <article className="bg-obsidian-surface border border-obsidian-border hover:border-obsidian-accent/30 transition-colors">
      {/* Header */}
      <header className="flex items-center gap-3 px-4 py-3">
        <Avatar avatarUrl={artist.avatar_url} displayName={artist.display_name} />

        <div className="flex-1 min-w-0">
          <div className="font-inter font-medium text-sm text-white/90 truncate">
            {artist.display_name}
          </div>
          {artist.slug && (
            <div className="font-sf-mono text-xs text-white/50 truncate">
              @{artist.slug}
            </div>
          )}
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {artist.ranking !== null && (
            <span className="font-sf-mono text-xs text-white/50">
              #{artist.ranking}
            </span>
          )}
          {artist.in_top_200 && (
            <span className="font-sf-mono text-xs px-1.5 py-0.5 bg-obsidian-accent/10 text-obsidian-accent border border-obsidian-accent/30">
              Top200
            </span>
          )}
          <span
            className={`w-2 h-2 rounded-full ${ACTIVITY_DOT[artist.activity_state]}`}
            title={activityTooltip}
          />
        </div>
      </header>

      {/* Stats */}
      <div className="border-t border-obsidian-border px-4 py-3 space-y-1.5">
        {/* Row 1: library, reposts, hit_rate */}
        {(show('library') || show('reposts') || show('hit_rate')) && (
          <div className="flex flex-wrap gap-3">
            {show('library') && (
              <ArtistStatChip
                icon={Music}
                label=""
                value={`${artist.library_track_count} tracks`}
                tooltip="tracks in your library from this artist"
              />
            )}
            {show('reposts') && (
              <ArtistStatChip
                icon={RefreshCw}
                label=""
                value={`${artist.repost_in_library_count} reposts`}
                tooltip="reposts from this artist in your library"
              />
            )}
            {show('hit_rate') && (
              <ArtistStatChip
                icon={Target}
                label="hit"
                value={hitRateValue}
                tooltip="proportion of feed tracks loved"
                accent={artist.hit_rate !== null && artist.hit_rate >= 0.15}
              />
            )}
          </div>
        )}

        {/* Row 2: first_loved anchor */}
        {show('first_loved') && firstLovedText && (
          <div className="flex">
            <span className="font-sf-mono text-xs text-white/50 truncate">
              {firstLovedText}
            </span>
          </div>
        )}

        {/* Row 3: feed_noise, activity */}
        {(show('feed_noise') || show('activity')) && (
          <div className="flex flex-wrap gap-3">
            {show('feed_noise') && (
              <ArtistStatChip
                icon={Radio}
                label="feed"
                value={feedNoiseValue}
                tooltip="average tracks per day in feed (last 7 days)"
              />
            )}
            {show('activity') && artist.last_activity_at !== null && (
              <ArtistStatChip
                icon={Radio}
                label="active"
                value={relativeTime(artist.last_activity_at)}
                tooltip={activityTooltip}
              />
            )}
          </div>
        )}

        {/* Row 4: elo, followers */}
        {(show('elo') || show('followers')) && (
          <div className="flex flex-wrap gap-3">
            {show('elo') && artist.avg_elo !== null && (
              <ArtistStatChip
                icon={Star}
                label="ELO"
                value={Math.round(artist.avg_elo)}
                tooltip="average ELO rating of loved tracks from this artist"
                accent={artist.avg_elo >= 1400}
              />
            )}
            {show('followers') && artist.follower_count !== null && (
              <ArtistStatChip
                icon={Users}
                label=""
                value={`${formatFollowers(artist.follower_count)} followers`}
                tooltip={`${artist.follower_count.toLocaleString()} followers on SoundCloud`}
              />
            )}
          </div>
        )}
      </div>

      {/* Footer */}
      <footer className="border-t border-obsidian-border px-4 py-2 flex gap-2 justify-end">
        <Button
          variant="outline"
          size="sm"
          onClick={handleUnfollow}
          disabled={!artist.is_following || isUnfollowing}
        >
          Unfollow
        </Button>
        <Button
          variant="ghost"
          size="sm"
          onClick={handleDetails}
        >
          Details
        </Button>
        <Button
          variant="ghost"
          size="sm"
          className="px-2"
          aria-label="More options"
        >
          <MoreHorizontal size={16} />
        </Button>
      </footer>
    </article>
  );
}
