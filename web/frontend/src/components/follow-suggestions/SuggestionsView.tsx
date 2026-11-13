import { useState } from 'react';
import type { ReactElement } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import type { Suggestion } from '../../api/followSuggestions';
import {
  useDismissSuggestion, useFollowAccount, useFollowSuggestions, usePendingAccountKeys, useSetSuggestionLabel,
} from '../../hooks/useFollowSuggestions';
import { Button } from '../ui/button';
import { ConnectionsSection } from './ConnectionsSection';
import { SuggestionRow } from './SuggestionRow';
import type { SuggestionHandlers } from './SuggestionRow';
import { UntieredSection } from './UntieredSection';

function useSuggestionHandlers(): SuggestionHandlers {
  const follow = useFollowAccount();
  const dismiss = useDismissSuggestion();
  const label = useSetSuggestionLabel();
  const pending = usePendingAccountKeys();
  return {
    // One follow at a time: every Follow button waits for the request in flight.
    followDisabled: follow.isPending,
    // One change per account at a time, so rollbacks never cross.
    isBusy: (a) => pending.has(a.key) || (a.soundcloud_user_id != null && pending.has(a.soundcloud_user_id)),
    onFollow: (id) => follow.mutate(id),
    onDismiss: (key) => dismiss.mutate(key),
    onSetLabel: (key, isLabel) => label.mutate({ key, isLabel }),
  };
}

function SuggestionList({ rows, handlers }: { rows: Suggestion[]; handlers: SuggestionHandlers }): ReactElement {
  return (
    <ul>
      {rows.map((s) => <SuggestionRow key={s.key} suggestion={s} handlers={handlers} />)}
    </ul>
  );
}

function LabelsSection({ rows, handlers }: { rows: Suggestion[]; handlers: SuggestionHandlers }): ReactElement | null {
  const [open, setOpen] = useState(false);
  if (rows.length === 0) return null;
  const Icon = open ? ChevronDown : ChevronRight;
  return (
    <section className="mt-10">
      <button type="button" aria-expanded={open} onClick={() => setOpen((o) => !o)} className="flex items-center gap-1 font-inter text-sm text-white/50 hover:text-white/80">
        <Icon className="w-4 h-4" /> Labels & channels ({rows.length})
      </button>
      {open && <SuggestionList rows={rows} handlers={handlers} />}
    </section>
  );
}

function ArtistsSection({ rows, handlers }: { rows: Suggestion[]; handlers: SuggestionHandlers }): ReactElement {
  return (
    <section aria-labelledby="fs-artists">
      <h2 id="fs-artists" className="font-inter text-lg font-semibold text-white">Artists to follow</h2>
      {rows.length === 0
        ? <p className="mt-3 font-sf-mono text-sm text-white/40">No suggestions right now.</p>
        : <SuggestionList rows={rows} handlers={handlers} />}
    </section>
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

export function SuggestionsView(): ReactElement {
  const { data, error, refetch } = useFollowSuggestions();
  const handlers = useSuggestionHandlers();
  return (
    <div className="max-w-4xl mx-auto">
      {data
        ? <ArtistsSection rows={data.artists} handlers={handlers} />
        : <SuggestionsStatus error={error} onRetry={() => void refetch()} />}
      <ConnectionsSection handlers={handlers} />
      {data && <LabelsSection rows={data.labels} handlers={handlers} />}
      <UntieredSection />
    </div>
  );
}
