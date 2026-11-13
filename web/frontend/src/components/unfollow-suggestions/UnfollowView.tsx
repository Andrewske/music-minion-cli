import { useState } from 'react';
import type { ReactElement } from 'react';
import type { UnfollowCandidate, UnfollowSection, UnfollowSuggestionsResponse } from '../../api/unfollowSuggestions';
import {
  SECTIONS, useBulkUnfollow, useKeepFollowing, usePendingUnfollowIds, useUnfollowCandidate, useUnfollowSuggestions,
} from '../../hooks/useUnfollowSuggestions';
import type { BulkUnfollow } from '../../hooks/useUnfollowSuggestions';
import { FollowingMeter, ViewTabs } from '../follow-suggestions/ViewTabs';
import { Button } from '../ui/button';
import { BulkProgressBar, ConfirmBulkDialog } from './BulkUnfollow';
import { CandidateRow } from './CandidateRow';
import type { CandidateHandlers } from './CandidateRow';

const LABELS: Record<UnfollowSection, string> = {
  redundant: 'Redundant reposters', dormant: 'Dormant', labels: 'Labels & channels', low_yield: 'Low yield',
};

const BLURBS: Record<UnfollowSection, string> = {
  redundant: 'Busy feeds where almost every track you liked also came from someone else. Most noise first.',
  dormant: 'Nothing posted or reposted since the feed history began.',
  labels: 'Label, collective, promo and repost channels. Fewest finds first.',
  low_yield: 'Everyone else, fewest finds that only they brought you first.',
};

function useCandidateHandlers(bulkRunning: boolean): CandidateHandlers {
  const unfollow = useUnfollowCandidate();
  const keep = useKeepFollowing();
  const pending = usePendingUnfollowIds();
  return {
    disabled: bulkRunning,
    isBusy: (id) => pending.has(id),
    onUnfollow: (id) => unfollow.mutate(id),
    onKeep: (id) => keep.mutate(id),
  };
}

interface SectionProps {
  section: UnfollowSection;
  rows: UnfollowCandidate[];
  handlers: CandidateHandlers;
  bulk: BulkUnfollow;
}

/** Low yield accounts still bring finds of their own: unfollow those one by one. */
const BULK_SECTIONS: ReadonlySet<UnfollowSection> = new Set(['redundant', 'dormant', 'labels']);

function SectionHeader({ section, rows, bulk }: Omit<SectionProps, 'handlers'>): ReactElement {
  const [confirming, setConfirming] = useState(false);
  // Tiered artists are never bulk-unfollowed; they stay listed for a one-by-one call.
  const untiered = rows.filter((r) => !r.tier);
  const confirm = (): void => {
    setConfirming(false);
    void bulk.run(untiered.map((r) => r.discovery_artist_id));
  };
  return (
    <div className="mb-2 flex flex-col sm:flex-row sm:items-start gap-2 sm:justify-between">
      <p className="font-inter text-sm text-white/50">{BLURBS[section]}</p>
      {BULK_SECTIONS.has(section) && untiered.length > 0 && (
        <Button size="sm" variant="destructive" className="shrink-0" disabled={bulk.progress != null} onClick={() => setConfirming(true)}>
          Unfollow {untiered.length.toLocaleString()} untiered
        </Button>
      )}
      <ConfirmBulkDialog
        count={untiered.length} skipped={rows.length - untiered.length} section={LABELS[section]}
        open={confirming} onOpenChange={setConfirming} onConfirm={confirm}
      />
    </div>
  );
}

function SectionList({ section, rows, handlers, bulk }: SectionProps): ReactElement {
  return (
    <section aria-label={LABELS[section]}>
      <SectionHeader section={section} rows={rows} bulk={bulk} />
      {rows.length === 0
        ? <p className="mt-3 font-sf-mono text-sm text-white/40">Nobody here right now.</p>
        : <ul>{rows.map((c) => <CandidateRow key={c.discovery_artist_id} candidate={c} handlers={handlers} />)}</ul>}
    </section>
  );
}

function Status({ error, onRetry }: { error: Error | null; onRetry: () => void }): ReactElement {
  if (!error) return <p className="font-sf-mono text-sm text-white/40">Loading suggestions…</p>;
  return (
    <div className="bg-red-500/5 border border-red-500/20 px-5 py-4 space-y-3">
      <p className="font-sf-mono text-sm text-red-400">{error.message}</p>
      <Button variant="outline" size="sm" onClick={onRetry}>Retry</Button>
    </div>
  );
}

const sectionCounts = (data: UnfollowSuggestionsResponse | undefined): Record<UnfollowSection, number> =>
  Object.fromEntries(SECTIONS.map((s) => [s, data?.sections[s].length ?? 0])) as Record<UnfollowSection, number>;

export function UnfollowView(): ReactElement {
  const { data, error, refetch } = useUnfollowSuggestions();
  const bulk = useBulkUnfollow();
  const handlers = useCandidateHandlers(bulk.progress != null);
  const [view, setView] = useState<UnfollowSection>('redundant');
  return (
    <div className="max-w-4xl mx-auto">
      {data && <FollowingMeter following={data.following} />}
      <ViewTabs view={view} counts={sectionCounts(data)} labels={LABELS} onChange={setView} />
      {bulk.progress && <BulkProgressBar progress={bulk.progress} stopping={bulk.stopping} onStop={bulk.stop} />}
      {data
        ? <SectionList section={view} rows={data.sections[view]} handlers={handlers} bulk={bulk} />
        : <Status error={error} onRetry={() => void refetch()} />}
    </div>
  );
}
