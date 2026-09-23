import { createFileRoute } from '@tanstack/react-router';
import type { FeedRankPreset, FeedSort, FeedSource } from '../api/feed';
import { FeedPage } from '../components/feed/FeedPage';

export type FeedSearch = {
  source?: FeedSource;
  maxRank?: FeedRankPreset;
  inLibrary?: boolean;
  showHidden?: boolean;
  sort?: FeedSort;
  minScore?: number;
};

const SOURCES: FeedSource[] = ['all', 'releases', 'reposts'];
const RANKS: FeedRankPreset[] = [25, 50, 75, 100, 200];
export const MIN_SCORE_PRESETS = [0.5, 0.7, 0.9] as const;

export const Route = createFileRoute('/feed')({
  component: FeedPage,
  validateSearch: (search: Record<string, unknown>): FeedSearch => {
    const source = SOURCES.includes(search.source as FeedSource)
      ? (search.source as FeedSource)
      : undefined;
    const parsedRank = Number(search.maxRank);
    const maxRank = RANKS.includes(parsedRank as FeedRankPreset)
      ? (parsedRank as FeedRankPreset)
      : search.top200 === true || search.top200 === 'true'
        ? 200
        : undefined;
    const parsedMinScore = Number(search.minScore);
    const minScore = MIN_SCORE_PRESETS.includes(parsedMinScore as (typeof MIN_SCORE_PRESETS)[number])
      ? parsedMinScore
      : undefined;
    return {
      source: source === 'all' ? undefined : source,
      maxRank,
      inLibrary: search.inLibrary === true || search.inLibrary === 'true' || undefined,
      showHidden: search.showHidden === true || search.showHidden === 'true' || undefined,
      sort: search.sort === 'score' ? 'score' : undefined,
      minScore,
    };
  },
});
