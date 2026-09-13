import type { FeedDecision, FeedItem, FeedRankPreset, FeedSource } from '@music-minion/shared';
import { FEED_RANK_PRESETS, applyFeedDecision } from '@music-minion/shared';

export interface FeedScreenState {
  source: FeedSource;
  maxRank?: FeedRankPreset;
  inLibrary: boolean;
}

type SearchValue = string | string[] | undefined;

const first = (value: SearchValue): string | undefined =>
  Array.isArray(value) ? value[0] : value;

export function parseFeedScreenState(params: {
  source?: SearchValue;
  maxRank?: SearchValue;
  inLibrary?: SearchValue;
}): FeedScreenState {
  const rawSource = first(params.source);
  const source: FeedSource =
    rawSource === 'releases' || rawSource === 'reposts' ? rawSource : 'all';
  const rank = Number(first(params.maxRank));
  const maxRank = FEED_RANK_PRESETS.find((preset) => preset === rank);
  const inLibrary = first(params.inLibrary) === 'true';
  return { source, maxRank, inLibrary };
}

export function optimisticallyDecideFeedItems(
  items: FeedItem[],
  soundcloudId: string,
  decision: FeedDecision
): FeedItem[] {
  if (decision !== 'keep') {
    return items.filter((item) => item.soundcloud_id !== soundcloudId);
  }
  return items.map((item) =>
    item.soundcloud_id === soundcloudId ? applyFeedDecision(item, decision) : item
  );
}
