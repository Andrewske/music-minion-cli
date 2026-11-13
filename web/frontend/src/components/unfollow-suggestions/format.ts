import type { UnfollowCandidate } from '../../api/unfollowSuggestions';
import { ageLabel } from '../follow-suggestions/format';

/** Chips like ["2,888 in feed", "117 liked/kept", "2 only from them", "last find 5 mo ago"]. */
export function candidateChips(c: UnfollowCandidate, now: number = Date.now()): string[] {
  if (c.items === 0) return ['nothing in the feed'];
  const chips = [
    `${c.items.toLocaleString()} in feed`,
    `${Math.round(c.noise_per_month).toLocaleString()}/mo`,
    `${c.good.toLocaleString()} liked/kept`,
    `${c.unique_finds} only from them`,
    c.liked_uploads > 0 ? `${c.liked_uploads} liked uploads` : null,
    c.last_find_at ? `last find ${ageLabel(c.last_find_at, now)}` : null,
  ];
  return chips.filter((chip): chip is string => chip !== null);
}

export const candidateName = (c: UnfollowCandidate): string => c.display_name || c.slug;
