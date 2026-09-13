import type { ArtistStats } from '../../api/artists';

const PRIOR = 0.22;

type KeepRateFields = Pick<
  ArtistStats,
  'upload_keep_rate' | 'upload_rated_count' | 'repost_keep_rate' | 'repost_rated_count'
>;

function formatRole(rate: number | null, rated: number): string {
  if (rate === null || rated <= 0) return '—';
  return `${Math.round(rate * 100)}% (${rated < 10 ? rated.toFixed(1) : Math.round(rated)})`;
}

/** "up 34% (12) · re 18% (4.5)" — uploader and reposter keep rates with rated weight. */
export function formatKeepRates(stats: KeepRateFields): string {
  return `up ${formatRole(stats.upload_keep_rate, stats.upload_rated_count)} · re ${formatRole(stats.repost_keep_rate, stats.repost_rated_count)}`;
}

/** Accent when either measured role beats the population prior. */
export function keepRateAccent(stats: KeepRateFields): boolean {
  return (stats.upload_keep_rate ?? 0) > PRIOR || (stats.repost_keep_rate ?? 0) > PRIOR;
}
