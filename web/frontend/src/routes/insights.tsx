import { createFileRoute } from '@tanstack/react-router';
import { DEFAULT_INSIGHT_MIN_COUNT, INSIGHT_TABS, type InsightSort } from '../api/insights';
import { InsightsPage } from '../components/insights/InsightsPage';
import { parseMinCount } from '../components/insights/insightsView';

export type InsightsSearch = {
  /** Omitted for the first tab (Keywords). */
  tab?: string;
  /** Omitted for the default of 8. */
  minCount?: number;
  /** Omitted for the default lift sort. */
  sort?: InsightSort;
};

export const Route = createFileRoute('/insights')({
  component: InsightsPage,
  validateSearch: (search: Record<string, unknown>): InsightsSearch => {
    const tab = INSIGHT_TABS.slice(1).find((item) => item.key === search.tab)?.key;
    const minCount = parseMinCount(search.minCount);
    return {
      tab,
      minCount: minCount === DEFAULT_INSIGHT_MIN_COUNT ? undefined : minCount,
      sort: search.sort === 'count' ? 'count' : undefined,
    };
  },
});
