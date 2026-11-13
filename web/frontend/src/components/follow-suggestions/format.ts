import type { Suggestion, SuggestionRole } from '../../api/followSuggestions';
import type { ArtistTier } from '../../api/artists';

const DAY_MS = 86_400_000;

export const ROLE_LABEL: Record<SuggestionRole, string> = {
  uploaded: 'uploaded',
  original: 'original',
  remixer: 'remix',
  feat: 'feat',
  remixed_by_others: 'remixed by others',
  kept: 'kept',
};

/** Coarse age for chips: "4d ago", "3 wk ago", "5 mo ago", "2 yr ago". */
export function ageLabel(iso: string, now: number = Date.now()): string {
  const days = Math.max(0, Math.floor((now - new Date(iso).getTime()) / DAY_MS));
  if (days < 1) return 'today';
  if (days < 14) return `${days}d ago`;
  if (days < 60) return `${Math.floor(days / 7)} wk ago`;
  if (days < 365) return `${Math.floor(days / 30)} mo ago`;
  return `${Math.floor(days / 365)} yr ago`;
}

const plural = (n: number, word: string): string => `${n} ${word}${n === 1 ? '' : 'es'}`;

/** Chips like ["12 liked", "4 remixes", "last like 3 wk ago", "posts 4/mo"]; zero counts are skipped. */
export function scoreChips(s: Suggestion, now: number = Date.now()): string[] {
  const e = s.evidence;
  const liked = e.uploaded + e.original;
  const chips = [
    liked > 0 ? `${liked} liked` : null,
    e.remixer > 0 ? plural(e.remixer, 'remix') : null,
    e.feat > 0 ? `${e.feat} feat` : null,
    e.remixed_by_others > 0 ? `remixed ${e.remixed_by_others}×` : null,
    e.kept > 0 ? `${e.kept} kept` : null,
    s.last_liked_at ? `last like ${ageLabel(s.last_liked_at, now)}` : null,
    activityChip(s),
  ];
  return chips.filter((c): c is string => c !== null);
}

function activityChip(s: Suggestion): string | null {
  if (!s.activity) return null;
  const perMonth = Math.round((s.activity.uploads_90d + s.activity.reposts_90d) / 3);
  return perMonth > 0 ? `posts ${perMonth}/mo` : 'quiet 90d';
}

export const soundcloudUrl = (permalink: string): string => `https://soundcloud.com/${permalink}`;

export const soundcloudSearchUrl = (name: string): string =>
  `https://soundcloud.com/search/people?q=${encodeURIComponent(name)}`;

export function formatFollowers(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1).replace(/\.0$/, '')}m`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1).replace(/\.0$/, '')}k`;
  return String(n);
}

const TIERS: ReadonlySet<string> = new Set<ArtistTier>(['S', 'A', 'B', 'C', 'D']);

export const asTier = (tier: string): ArtistTier | null => (TIERS.has(tier) ? (tier as ArtistTier) : null);
