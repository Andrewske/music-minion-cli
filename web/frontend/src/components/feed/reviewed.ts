import type { FeedDecision, ReviewedItem } from '../../api/feed';
import { formatListenTime } from '../../lib/feedListen';

export const REVIEWED_QUERY_KEY = ['feed-reviewed'] as const;
export const REVIEWED_FILTERS: ReadonlyArray<FeedDecision | undefined> = [
  undefined,
  'keep',
  'not_quite',
  'nope',
];

export function formatDecidedAt(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '-';
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

/** "0:42 played · reached 1:30": time played, then furthest position. */
export function describeListen(item: Pick<ReviewedItem, 'listen_seconds' | 'max_position_ms'>): string {
  if (item.listen_seconds === null) return 'Not tracked';
  const reached =
    item.max_position_ms === null ? '' : ` · reached ${formatListenTime(item.max_position_ms / 1000)}`;
  return `${formatListenTime(item.listen_seconds)} played${reached}`;
}
