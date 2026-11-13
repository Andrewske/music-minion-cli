import { useState } from 'react';
import type { ReactElement } from 'react';
import type { FollowingCount, FollowSuggestionsResponse, Suggestion } from '../../api/followSuggestions';
import {
  useDismissSuggestion, useFollowAccount, useFollowConnections, useFollowSuggestions, useLinkSuggestion,
  usePendingAccountKeys, useSetSuggestionLabel, useUntieredFollows,
} from '../../hooks/useFollowSuggestions';
import { Button } from '../ui/button';
import { ConnectionsSection } from './ConnectionsSection';
import { SuggestionRow } from './SuggestionRow';
import type { SuggestionHandlers } from './SuggestionRow';
import { UntieredSection } from './UntieredSection';

const LOW_SLOTS = 25;

/** "1,945 / 2,000 following": SoundCloud stops follows at the limit. */
function FollowingMeter({ following }: { following: FollowingCount }): ReactElement {
  const left = following.limit - following.count;
  const tone = left <= 0 ? 'text-red-400' : left <= LOW_SLOTS ? 'text-amber-400' : 'text-white/50';
  const note = left <= 0 ? 'at the limit: unfollow someone first' : `${left.toLocaleString()} left`;
  return (
    <p data-testid="following-meter" className={`mb-3 font-sf-mono text-xs ${tone}`}>
      Following {following.count.toLocaleString()} / {following.limit.toLocaleString()} on SoundCloud · {note}
    </p>
  );
}

function useSuggestionHandlers(full: boolean): SuggestionHandlers {
  const follow = useFollowAccount();
  const dismiss = useDismissSuggestion();
  const label = useSetSuggestionLabel();
  const link = useLinkSuggestion();
  const pending = usePendingAccountKeys();
  return {
    // One follow at a time, and none once SoundCloud's following limit is reached.
    followDisabled: follow.isPending || full,
    // One change per account at a time, so rollbacks never cross.
    isBusy: (a) => pending.has(a.key) || (a.soundcloud_user_id != null && pending.has(a.soundcloud_user_id)),
    onFollow: (id) => follow.mutate(id),
    onDismiss: (key) => dismiss.mutate(key),
    onSetLabel: (key, isLabel) => label.mutate({ key, isLabel }),
    onLink: (key, url) => link.mutateAsync({ key, url }),
  };
}

function SuggestionList({ rows, handlers }: { rows: Suggestion[]; handlers: SuggestionHandlers }): ReactElement {
  return (
    <ul>
      {rows.map((s) => <SuggestionRow key={s.key} suggestion={s} handlers={handlers} />)}
    </ul>
  );
}

function ListSection({ id, title, rows, handlers }: { id: string; title: string; rows: Suggestion[]; handlers: SuggestionHandlers }): ReactElement {
  return (
    <section aria-labelledby={id}>
      <h2 id={id} className="font-inter text-lg font-semibold text-white">{title}</h2>
      {rows.length === 0
        ? <p className="mt-3 font-sf-mono text-sm text-white/40">No suggestions right now.</p>
        : <SuggestionList rows={rows} handlers={handlers} />}
    </section>
  );
}

type View = 'artists' | 'labels' | 'connections' | 'untiered';

/** Tab label counts; null hides a tab (its section has nothing to show). */
function useViewCounts(data: FollowSuggestionsResponse | undefined): Record<View, number | null> {
  const connections = useFollowConnections().data;
  const untiered = useUntieredFollows().data;
  const connectionCount = connections ? connections.co_credit.length + connections.favorites_follow.length : 0;
  const untieredCount = untiered ? untiered.recent.length + untiered.rated.length : 0;
  return {
    artists: data?.artists.length ?? 0,
    labels: data?.labels.length ?? 0,
    connections: connectionCount || null,
    untiered: untieredCount || null,
  };
}

const VIEW_LABELS: Record<View, string> = {
  artists: 'Artists', labels: 'Labels & channels', connections: 'Connections', untiered: 'New follows',
};

function ViewTabs({ view, counts, onChange }: { view: View; counts: Record<View, number | null>; onChange: (v: View) => void }): ReactElement {
  const views = (Object.keys(VIEW_LABELS) as View[]).filter((v) => counts[v] != null);
  return (
    <div role="tablist" className="mb-4 flex flex-wrap gap-1 border-b border-obsidian-border">
      {views.map((v) => (
        <button
          key={v}
          type="button"
          role="tab"
          aria-selected={view === v}
          onClick={() => onChange(v)}
          className={`px-3 py-2 -mb-px border-b-2 font-inter text-sm ${view === v ? 'border-obsidian-accent text-white' : 'border-transparent text-white/50 hover:text-white/80'}`}
        >
          {VIEW_LABELS[v]} <span className="font-sf-mono text-[11px] text-white/40">{counts[v]}</span>
        </button>
      ))}
    </div>
  );
}

function SuggestionsStatus({ error, onRetry }: { error: Error | null; onRetry: () => void }): ReactElement {
  if (!error) return <p className="font-sf-mono text-sm text-white/40">Loading suggestions…</p>;
  return (
    <div className="bg-red-500/5 border border-red-500/20 px-5 py-4 space-y-3">
      <p className="font-sf-mono text-sm text-red-400">{error.message}</p>
      <Button variant="outline" size="sm" onClick={onRetry}>Retry</Button>
    </div>
  );
}

function ActiveView({ view, data, handlers }: { view: View; data: FollowSuggestionsResponse; handlers: SuggestionHandlers }): ReactElement | null {
  if (view === 'labels') return <ListSection id="fs-labels" title="Labels & channels" rows={data.labels} handlers={handlers} />;
  if (view === 'connections') return <ConnectionsSection handlers={handlers} />;
  if (view === 'untiered') return <UntieredSection />;
  return <ListSection id="fs-artists" title="Artists to follow" rows={data.artists} handlers={handlers} />;
}

export function SuggestionsView(): ReactElement {
  const { data, error, refetch } = useFollowSuggestions();
  const handlers = useSuggestionHandlers(data != null && data.following.count >= data.following.limit);
  const counts = useViewCounts(data);
  const [picked, setView] = useState<View>('artists');
  // A tab whose section emptied out (all new follows tiered) falls back to artists.
  const view = counts[picked] == null ? 'artists' : picked;
  return (
    <div className="max-w-4xl mx-auto">
      {data && <FollowingMeter following={data.following} />}
      <ViewTabs view={view} counts={counts} onChange={setView} />
      {data
        ? <ActiveView view={view} data={data} handlers={handlers} />
        : <SuggestionsStatus error={error} onRetry={() => void refetch()} />}
    </div>
  );
}
