import { useState } from 'react';
import type { StoriesArtist } from '../../api/stories';
import { unheardCount } from './storiesQueue';

const artistName = (artist: StoriesArtist): string => artist.display_name ?? artist.slug;

export function ArtistAvatar({ artist, size }: { artist: StoriesArtist; size: number }): JSX.Element {
  const [failed, setFailed] = useState(false);
  if (artist.avatar_url && !failed) {
    return (
      <img
        src={artist.avatar_url}
        alt=""
        width={size}
        height={size}
        loading="lazy"
        onError={() => setFailed(true)}
        className="shrink-0 rounded-full object-cover"
        style={{ width: size, height: size }}
      />
    );
  }
  return (
    <span
      aria-hidden="true"
      className="flex shrink-0 items-center justify-center rounded-full bg-linear-to-br/srgb from-obsidian-accent/30 to-obsidian-surface text-xs font-semibold text-white/70"
      style={{ width: size, height: size }}
    >
      {artistName(artist).slice(0, 1).toUpperCase()}
    </span>
  );
}

interface ArtistRowProps {
  artist: StoriesArtist;
  isActive: boolean;
  onSelect: (artistId: number) => void;
}

function ArtistRow({ artist, isActive, onSelect }: ArtistRowProps): JSX.Element {
  const unheard = unheardCount(artist);
  return (
    <li>
      <button
        type="button"
        onClick={() => onSelect(artist.discovery_artist_id)}
        aria-current={isActive ? 'true' : undefined}
        aria-label={`${artistName(artist)}, ${unheard} unheard`}
        className={`flex w-full items-center gap-3 rounded-full py-1.5 pl-1.5 pr-3 text-left transition-colors focus-visible:outline-solid focus-visible:outline-2 focus-visible:outline-obsidian-accent ${
          isActive ? 'bg-white/10 text-white' : 'text-white/70 hover:bg-white/5 hover:text-white'
        }`}
      >
        <span className="relative">
          <ArtistAvatar artist={artist} size={40} />
          {unheard > 0 && (
            <span className="absolute -right-1 -top-1 min-w-4 rounded-full bg-obsidian-accent px-1 text-center font-sf-mono text-[10px] leading-4 text-black">
              {unheard}
            </span>
          )}
        </span>
        <span className={`truncate text-sm ${isActive ? 'font-semibold' : 'font-medium'}`}>{artistName(artist)}</span>
      </button>
    </li>
  );
}

interface StoriesArtistListProps {
  artists: readonly StoriesArtist[];
  activeArtistId: number | null;
  onSelect: (artistId: number) => void;
}

/** "Latest from people you follow": one row per artist with an unheard-count badge. */
export function StoriesArtistList({ artists, activeArtistId, onSelect }: StoriesArtistListProps): JSX.Element {
  return (
    <nav aria-label="Followed artists">
      <ul className="flex flex-col gap-1">
        {artists.map((artist) => (
          <ArtistRow
            key={artist.discovery_artist_id}
            artist={artist}
            isActive={artist.discovery_artist_id === activeArtistId}
            onSelect={onSelect}
          />
        ))}
      </ul>
    </nav>
  );
}
