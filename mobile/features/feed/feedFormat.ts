/**
 * Pure formatting for the Feed card and filter row.
 */
import { FEED_RANK_PRESETS, getFeedItemUploader } from '@music-minion/shared';
import type { FeedArtist, FeedItem, FeedRankPreset, FeedSource } from '@music-minion/shared';

export interface AttributionLine {
  prefix: 'Uploaded by' | 'Reposted by';
  artist: FeedArtist;
  /** Discovery-artist rank of the named artist, e.g. "#150". Null when unranked. */
  rankLabel: string | null;
  /** "+5 others", or null when nobody else reposted. */
  othersLabel: string | null;
}

export interface FilterOption {
  key: string;
  label: string;
  testID: string;
}

export const formatRank = (rank: number | null | undefined): string | null =>
  rank === null || rank === undefined ? null : `#${rank}`;

export const formatOthers = (count: number): string | null =>
  count <= 0 ? null : `+${count} ${count === 1 ? 'other' : 'others'}`;

export const artistName = (artist: FeedArtist): string => artist.display_name ?? artist.slug;

const rankOrInfinity = (artist: FeedArtist): number => artist.ranking ?? Number.POSITIVE_INFINITY;

/**
 * The reposter to name on the card: the best (lowest) ranked one, so "+N others"
 * never hides the rank the feed scored on. Ties and all-unranked keep API order.
 */
export function pickLeadReposter(reposters: readonly FeedArtist[]): FeedArtist | null {
  return reposters.reduce<FeedArtist | null>(
    (best, candidate): FeedArtist | null => (best === null || rankOrInfinity(candidate) < rankOrInfinity(best) ? candidate : best),
    null
  );
}

export function uploadAttribution(item: FeedItem): AttributionLine | null {
  const uploader = getFeedItemUploader(item);
  if (!item.sources.includes('release') || uploader === null) return null;
  return { prefix: 'Uploaded by', artist: uploader, rankLabel: formatRank(uploader.ranking), othersLabel: null };
}

export function repostAttribution(item: FeedItem): AttributionLine | null {
  const lead = pickLeadReposter(item.reposters);
  if (!item.sources.includes('repost') || lead === null) return null;
  const total = Math.max(item.reposter_count, item.reposters.length);
  return {
    prefix: 'Reposted by',
    artist: lead,
    rankLabel: formatRank(lead.ranking),
    othersLabel: formatOthers(total - 1),
  };
}

export const feedAttributions = (item: FeedItem): AttributionLine[] =>
  [uploadAttribution(item), repostAttribution(item)].filter(
    (line): line is AttributionLine => line !== null
  );

export const formatKeepScore = (probability: number): string => `${Math.round(probability * 100)}% keep`;

export const isLikelyKeep = (probability: number): boolean => probability >= 0.7;

const SOURCE_LABELS: Record<FeedSource, string> = { all: 'All', releases: 'Releases', reposts: 'Reposts' };

export const SOURCE_OPTIONS: readonly FilterOption[] = (['all', 'releases', 'reposts'] as const).map((key): FilterOption => ({
  key,
  label: SOURCE_LABELS[key],
  testID: `feed-source-${key}`,
}));

export const RANK_OPTIONS: readonly FilterOption[] = [
  { key: 'all', label: 'All ranks', testID: 'feed-rank-all' },
  ...FEED_RANK_PRESETS.map((rank): FilterOption => ({ key: String(rank), label: `Top ${rank}`, testID: `feed-rank-${rank}` })),
];

export const sourceChipLabel = (source: FeedSource): string => `Source: ${SOURCE_LABELS[source]}`;

export const rankChipLabel = (maxRank: FeedRankPreset | undefined): string =>
  `Rank: ${maxRank === undefined ? 'All' : `Top ${maxRank}`}`;

export const rankKey = (maxRank: FeedRankPreset | undefined): string =>
  maxRank === undefined ? 'all' : String(maxRank);

export const sourceFromKey = (key: string): FeedSource =>
  key === 'releases' || key === 'reposts' ? key : 'all';

export const rankFromKey = (key: string): FeedRankPreset | undefined =>
  FEED_RANK_PRESETS.find((preset): boolean => String(preset) === key);
