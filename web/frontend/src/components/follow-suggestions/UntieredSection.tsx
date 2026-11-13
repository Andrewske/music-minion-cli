import type { ReactElement } from 'react';
import { Link } from '@tanstack/react-router';
import type { UntieredArtist } from '../../api/followSuggestions';
import type { ArtistTier } from '../../api/artists';
import { useTierUntiered, useUntieredFollows } from '../../hooks/useFollowSuggestions';
import { TIER_COLORS } from '../artists/RankTierMenu';
import { Avatar, Chip } from './AccountRow';
import { ageLabel } from './format';

const TIER_CHOICES: ArtistTier[] = ['S', 'A', 'B', 'C'];

function TierButtons({ artist, onTier }: { artist: UntieredArtist; onTier: (tier: ArtistTier) => void }): ReactElement {
  return (
    <div className="flex gap-1" role="group" aria-label={`Tier for ${artist.display_name}`}>
      {TIER_CHOICES.map((t) => (
        <button key={t} type="button" onClick={() => onTier(t)} aria-pressed={artist.tier === t} className={`font-sf-mono text-xs w-8 h-8 border ${TIER_COLORS[t]} hover:brightness-125 ${artist.tier === t ? 'ring-1 ring-white/70' : ''}`}>
          {t}
        </button>
      ))}
    </div>
  );
}

function UntieredRow({ artist, showRates, onTier }: { artist: UntieredArtist; showRates: boolean; onTier: (tier: ArtistTier) => void }): ReactElement {
  return (
    <li data-testid={`untiered-row-${artist.discovery_artist_id}`} className="flex items-center gap-3 border-b border-obsidian-border py-2">
      <Avatar url={artist.avatar_url} name={artist.display_name} size={32} />
      <div className="min-w-0 flex-1">
        <Link to="/artists/$artistId" params={{ artistId: String(artist.discovery_artist_id) }} className="block font-inter text-sm text-white truncate hover:underline">
          {artist.display_name}
        </Link>
        <div className="mt-0.5 flex flex-wrap gap-1.5">
          {artist.followed_at && <Chip>followed {ageLabel(artist.followed_at)}</Chip>}
          {artist.tier && <Chip>auto tier {artist.tier}</Chip>}
          {showRates && artist.keep_rate != null && <Chip>{Math.round(artist.keep_rate * 100)}% kept</Chip>}
          {showRates && <Chip>{Number.isInteger(artist.rated_count) ? artist.rated_count : artist.rated_count.toFixed(1)} rated</Chip>}
        </div>
      </div>
      <TierButtons artist={artist} onTier={onTier} />
    </li>
  );
}

function UntieredList({ title, rows, showRates }: { title: string; rows: UntieredArtist[]; showRates: boolean }): ReactElement | null {
  const tierMut = useTierUntiered();
  if (rows.length === 0) return null;
  return (
    <div className="mt-4">
      <h3 className="font-sf-mono text-xs uppercase tracking-wide text-white/40">{title}</h3>
      <ul>
        {rows.map((a) => (
          <UntieredRow key={a.discovery_artist_id} artist={a} showRates={showRates} onTier={(tier) => tierMut.mutate({ id: a.discovery_artist_id, tier })} />
        ))}
      </ul>
    </div>
  );
}

export function UntieredSection(): ReactElement | null {
  const { data } = useUntieredFollows();
  if (!data || (data.recent.length === 0 && data.rated.length === 0)) return null;
  return (
    <section aria-labelledby="fs-untiered">
      <h2 id="fs-untiered" className="font-inter text-lg font-semibold text-white">New follows to tier</h2>
      <UntieredList title="Recently followed" rows={data.recent} showRates={false} />
      <UntieredList title="Rated tracks, no tier yet" rows={data.rated} showRates />
    </section>
  );
}
