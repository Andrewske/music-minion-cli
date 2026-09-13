import { useState } from 'react';
import type { ReactElement, ChangeEvent, KeyboardEvent, SyntheticEvent } from 'react';
import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import { toast } from 'react-toastify';
import type { ArtistStats, ArtistTier } from '../../api/artists';
import { useUpdateArtist } from '../../hooks/useArtists';

export const TIER_COLORS: Record<ArtistTier, string> = {
  S: 'text-amber-300 border-amber-300/40 bg-amber-300/10',
  A: 'text-violet-300 border-violet-300/40 bg-violet-300/10',
  B: 'text-sky-300 border-sky-300/40 bg-sky-300/10',
  C: 'text-emerald-300 border-emerald-300/40 bg-emerald-300/10',
  D: 'text-slate-400 border-slate-500/40 bg-slate-500/10',
};

const TIERS: ArtistTier[] = ['S', 'A', 'B', 'C', 'D'];

export function TierBadge({ tier }: { tier: ArtistTier }): ReactElement {
  return (
    <span className={`font-sf-mono text-[10px] px-1 py-px border ${TIER_COLORS[tier]}`}>
      {tier}
    </span>
  );
}

interface RankTierMenuProps {
  artist: ArtistStats;
}

/**
 * Rank/tier editor for SoundCloud artists — the "#N" badge opens a menu.
 * Assigning a tier auto-renumbers rankings server-side (tier band + liked
 * count); the number input inserts the artist at an exact position.
 */
export function RankTierMenu({ artist }: RankTierMenuProps): ReactElement | null {
  const update = useUpdateArtist();
  const [rankInput, setRankInput] = useState('');

  if (artist.id == null) return null;
  const id = artist.id;

  const setTier = (tier: ArtistTier | null): void => {
    update.mutate(
      { id, body: { tier } },
      { onError: (err) => toast.error(err.message) },
    );
  };

  const submitRank = (e: SyntheticEvent<HTMLFormElement>): void => {
    e.preventDefault();
    const n = Number(rankInput);
    if (!Number.isInteger(n) || n < 1) return;
    update.mutate(
      { id, body: { ranking: n } },
      {
        onSuccess: () => setRankInput(''),
        onError: (err) => toast.error(err.message),
      },
    );
  };

  const handleRankChange = (e: ChangeEvent<HTMLInputElement>): void => {
    setRankInput(e.target.value.replace(/\D/g, ''));
  };

  // Keep DropdownMenu typeahead from stealing keystrokes typed in the input
  const stopTypeahead = (e: KeyboardEvent<HTMLInputElement>): void => {
    if (e.key !== 'Escape') e.stopPropagation();
  };

  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild>
        <button
          type="button"
          title="Edit rank / tier"
          className="flex items-center gap-1 hover:bg-white/5 px-1 py-0.5 transition-colors"
        >
          {artist.tier && <TierBadge tier={artist.tier} />}
          <span className="font-sf-mono text-xs text-white/50 hover:text-white transition-colors">
            #{artist.ranking ?? '—'}
          </span>
        </button>
      </DropdownMenu.Trigger>

      <DropdownMenu.Portal>
        <DropdownMenu.Content
          align="end"
          sideOffset={4}
          className="z-50 w-48 bg-obsidian-surface border border-obsidian-border p-3 shadow-lg space-y-3"
        >
          <div className="space-y-1.5">
            <p className="font-sf-mono text-[10px] uppercase tracking-widest text-white/40">
              Tier
            </p>
            <div className="flex gap-1">
              {TIERS.map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => setTier(t)}
                  disabled={update.isPending}
                  className={`w-7 h-7 border font-sf-mono text-xs transition-colors disabled:opacity-50 ${
                    t === artist.tier
                      ? TIER_COLORS[t]
                      : 'border-obsidian-border text-white/50 hover:text-white hover:border-white/30'
                  }`}
                >
                  {t}
                </button>
              ))}
            </div>
            {artist.tier && (
              <button
                type="button"
                onClick={() => setTier(null)}
                disabled={update.isPending}
                className="font-sf-mono text-[10px] text-white/40 hover:text-white transition-colors disabled:opacity-50"
              >
                Clear tier
              </button>
            )}
          </div>

          <div className="space-y-1.5">
            <p className="font-sf-mono text-[10px] uppercase tracking-widest text-white/40">
              Rank
            </p>
            <form onSubmit={submitRank} className="flex gap-1">
              <input
                type="text"
                inputMode="numeric"
                value={rankInput}
                onChange={handleRankChange}
                onKeyDown={stopTypeahead}
                placeholder={artist.ranking != null ? `#${artist.ranking}` : '#'}
                className="w-16 px-2 py-1 bg-obsidian-bg border border-obsidian-border text-white placeholder:text-white/30 font-sf-mono text-xs focus:outline-none focus:ring-1 focus:ring-obsidian-accent"
              />
              <button
                type="submit"
                disabled={update.isPending || rankInput === ''}
                className="px-2 py-1 border border-obsidian-border font-sf-mono text-xs text-white/60 hover:text-white hover:border-white/30 transition-colors disabled:opacity-50"
              >
                Set
              </button>
            </form>
          </div>
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}
