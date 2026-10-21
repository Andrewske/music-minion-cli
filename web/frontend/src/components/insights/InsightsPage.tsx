import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate, useSearch } from '@tanstack/react-router';
import { Loader2 } from 'lucide-react';
import {
  DEFAULT_INSIGHT_MIN_COUNT,
  INSIGHT_DIMENSION_LABELS,
  INSIGHT_TABS,
  formatKeepPct,
  getInsights,
  sortInsightRows,
  type InsightDimension,
  type InsightSort,
} from '../../api/insights';
import type { InsightsSearch } from '../../routes/insights';
import { InsightTable } from './InsightTable';
import { InsightTracksPanel } from './InsightTracksPanel';
import { INSIGHTS_QUERY_KEY, MAX_MIN_COUNT, parseMinCount, tabByKey } from './insightsView';

interface Selection {
  dimension: InsightDimension;
  value: string;
}

const EMPTY_TEXT: Partial<Record<InsightDimension, string>> = {
  tag: 'SoundCloud tags are stored for tracks ingested from now on; tracks reviewed earlier have none yet.',
};

interface DimensionSectionProps {
  dimension: InsightDimension;
  minCount: number;
  sort: InsightSort;
  selection: Selection | null;
  onSelect: (selection: Selection) => void;
}

function DimensionSection({ dimension, minCount, sort, selection, onSelect }: DimensionSectionProps): JSX.Element {
  const insightsQuery = useQuery({
    queryKey: [...INSIGHTS_QUERY_KEY, dimension, minCount],
    queryFn: () => getInsights(dimension, minCount),
  });
  const label = INSIGHT_DIMENSION_LABELS[dimension];
  if (insightsQuery.isLoading) {
    return <div className="flex justify-center py-8 text-white/40" role="status" aria-label={`Loading ${label}`}><Loader2 className="h-5 w-5 animate-spin" /></div>;
  }
  if (insightsQuery.isError || !insightsQuery.data) {
    return <p className="py-6 text-sm text-white/50" role="alert">Failed to load {label.toLowerCase()} insights</p>;
  }
  const rows = sortInsightRows(insightsQuery.data.rows, sort);
  if (rows.length === 0) {
    return <p className="py-6 text-sm text-white/40">{EMPTY_TEXT[dimension] ?? `No ${label.toLowerCase()} seen ${minCount}+ times yet.`}</p>;
  }
  const selectedValue = selection?.dimension === dimension ? selection.value : null;
  return <InsightTable label={label} rows={rows} selectedValue={selectedValue} onSelect={(row) => onSelect({ dimension, value: row.value })} />;
}

function OverallSummary(): JSX.Element | null {
  // min_count is irrelevant to the baseline; reuse the cheapest table.
  const overallQuery = useQuery({
    queryKey: [...INSIGHTS_QUERY_KEY, 'duration', DEFAULT_INSIGHT_MIN_COUNT],
    queryFn: () => getInsights('duration'),
  });
  const overall = overallQuery.data?.overall;
  if (!overall) return null;
  return (
    <p className="text-sm text-white/60">
      {overall.seen} reviewed tracks · overall keep {formatKeepPct(overall.keep_pct)} (a not quite counts as half). Flagged tracks and legacy hides are left out.
    </p>
  );
}

function useInsightsSearch(): { search: InsightsSearch; update: (changes: Partial<InsightsSearch>) => void } {
  const search = useSearch({ from: '/insights' });
  const navigate = useNavigate();
  const update = (changes: Partial<InsightsSearch>): void => {
    void navigate({ to: '/insights', search: { ...search, ...changes } });
  };
  return { search, update };
}

function Controls({ minCount, sort, update }: { minCount: number; sort: InsightSort; update: (changes: Partial<InsightsSearch>) => void }): JSX.Element {
  const [draft, setDraft] = useState(String(minCount));
  const commit = (): void => {
    const parsed = parseMinCount(draft);
    if (parsed === undefined) return setDraft(String(minCount));
    update({ minCount: parsed === DEFAULT_INSIGHT_MIN_COUNT ? undefined : parsed });
  };
  const toggle = (value: InsightSort): string =>
    `rounded px-3 py-1.5 text-xs ${sort === value ? 'bg-obsidian-accent/20 text-obsidian-accent' : 'text-white/60 hover:text-white'}`;
  return (
    <div className="flex flex-wrap items-center gap-3">
      <label className="flex items-center gap-2 text-xs text-white/60">
        Hide values seen fewer than
        <input
          type="number" min={1} max={MAX_MIN_COUNT} value={draft} aria-label="Minimum times seen"
          onChange={(event) => setDraft(event.target.value)} onBlur={commit} onKeyDown={(event) => event.key === 'Enter' && commit()}
          className="w-16 rounded border border-obsidian-border bg-black/30 px-2 py-1 font-sf-mono text-xs text-white"
        />
        times
      </label>
      <div className="flex rounded border border-obsidian-border" role="group" aria-label="Sort by">
        <button type="button" aria-pressed={sort === 'lift'} onClick={() => update({ sort: undefined })} className={toggle('lift')}>Lift</button>
        <button type="button" aria-pressed={sort === 'count'} onClick={() => update({ sort: 'count' })} className={toggle('count')}>Count</button>
      </div>
    </div>
  );
}

/** Which keywords, genres, tags and reposters predict keeps vs nopes. */
export function InsightsPage(): JSX.Element {
  const { search, update } = useInsightsSearch();
  const [selection, setSelection] = useState<Selection | null>(null);
  const activeTab = tabByKey(search.tab);
  const minCount = search.minCount ?? DEFAULT_INSIGHT_MIN_COUNT;
  const sort = search.sort ?? 'lift';
  const selectTab = (key: string): void => {
    setSelection(null);
    update({ tab: key === INSIGHT_TABS[0].key ? undefined : key });
  };
  return (
    <div className="min-h-screen bg-black p-6">
      <div className="mx-auto max-w-6xl space-y-5">
        <div className="space-y-1">
          <h1 className="text-3xl font-bold text-white">Insights</h1>
          <OverallSummary />
        </div>
        <div className="flex gap-1 overflow-x-auto border-b border-obsidian-border" role="tablist">
          {INSIGHT_TABS.map((tab) => (
            <button key={tab.key} type="button" role="tab" aria-selected={tab.key === activeTab.key} onClick={() => selectTab(tab.key)}
              className={`relative px-4 py-2.5 text-sm font-medium ${tab.key === activeTab.key ? 'text-obsidian-accent' : 'text-white/60 hover:text-white'}`}>
              {tab.label}
              {tab.key === activeTab.key && <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-obsidian-accent" />}
            </button>
          ))}
        </div>
        <Controls key={minCount} minCount={minCount} sort={sort} update={update} />
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,24rem)]">
          <div className="space-y-8">
            {activeTab.dimensions.map((dimension) => (
              <DimensionSection key={dimension} dimension={dimension} minCount={minCount} sort={sort} selection={selection} onSelect={setSelection} />
            ))}
          </div>
          {selection && (
            <div className="lg:sticky lg:top-6 lg:self-start">
              <InsightTracksPanel dimension={selection.dimension} value={selection.value} onClose={() => setSelection(null)} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
