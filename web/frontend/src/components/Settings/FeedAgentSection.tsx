import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Bot, Check, Loader2, RotateCcw, Sparkles, X } from 'lucide-react';
import { toast } from 'sonner';
import { FEED_QUERY_PREFIX, invalidateFlagViews } from '../feed/feedCache';
import {
  acceptRuleSuggestion,
  classifyAmbiguousTracks,
  describeClassifyResult,
  dismissRuleSuggestion,
  getClassifications,
  getRuleSuggestions,
  getUnreadableCount,
  mineRuleSuggestions,
  resolveClassification,
  retryUnreadable,
  type FeedClassification,
  type RuleSuggestion,
  type SuggestionOverrides,
} from '../../api/feedAgent';
import {
  FILTER_RULE_KIND_LABELS,
  FLAG_REASONS,
  FLAG_REASON_LABELS,
  formatConfidence,
  ruleCriterion,
  type FlagReason,
} from '../../api/feedFilters';
import { usePlayFeedRow } from '../../hooks/usePlayFeedRow';
import { formatFlagDuration, ruleErrorMessage } from '../feed/flagged';
import { FILTER_RULES_QUERY_KEY } from '../feed/reviewed';
import { CLASSIFICATIONS_QUERY_KEY, SUGGESTIONS_QUERY_KEY, UNREADABLE_QUERY_KEY, suggestionOverrides } from './feedAgent';

const FIELD = 'rounded border border-obsidian-border bg-black/30 px-2 py-1.5 text-sm text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-obsidian-accent';
const SMALL_BUTTON = 'flex min-h-9 items-center gap-1.5 rounded border border-obsidian-border px-3 text-xs text-white/70 hover:text-white disabled:opacity-50';

interface SuggestionRowProps {
  suggestion: RuleSuggestion;
  isBusy: boolean;
  onAccept: (suggestion: RuleSuggestion, overrides?: SuggestionOverrides) => void;
  onDismiss: (suggestion: RuleSuggestion) => void;
}

export function SuggestionRow({ suggestion, isBusy, onAccept, onDismiss }: SuggestionRowProps): JSX.Element {
  const [criterion, setCriterion] = useState(ruleCriterion(suggestion));
  const [reason, setReason] = useState<FlagReason>(suggestion.reason);
  return (
    <article aria-label={`Suggestion ${suggestion.name}`} className="space-y-2 rounded border border-obsidian-border bg-obsidian-surface px-3 py-2">
      <div>
        <p className="text-sm text-white">{suggestion.name}</p>
        <p className="text-xs text-white/50">{suggestion.evidence}</p>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[11px] text-white/40">{FILTER_RULE_KIND_LABELS[suggestion.kind]}</span>
        <input aria-label={`${suggestion.name} criterion`} value={criterion} onChange={(event) => setCriterion(event.target.value)} className={`${FIELD} min-w-40 flex-1 font-sf-mono text-xs`} />
        <select aria-label={`${suggestion.name} reason`} value={reason} onChange={(event) => setReason(event.target.value as FlagReason)} className={FIELD}>
          {FLAG_REASONS.map((value) => <option key={value} value={value}>{FLAG_REASON_LABELS[value]}</option>)}
        </select>
        <button type="button" disabled={isBusy} onClick={() => onAccept(suggestion, suggestionOverrides(suggestion, criterion, reason))} className={`${SMALL_BUTTON} hover:border-obsidian-accent hover:text-obsidian-accent`}>
          <Check className="h-3.5 w-3.5" /> Accept
        </button>
        <button type="button" disabled={isBusy} onClick={() => onDismiss(suggestion)} className={SMALL_BUTTON}>
          <X className="h-3.5 w-3.5" /> Dismiss
        </button>
      </div>
    </article>
  );
}

function useSuggestionMutations(): {
  mine: () => void;
  isMining: boolean;
  accept: (suggestion: RuleSuggestion, overrides?: SuggestionOverrides) => void;
  dismiss: (suggestion: RuleSuggestion) => void;
  busyId: number | null;
} {
  const queryClient = useQueryClient();
  const refresh = (): void => {
    void queryClient.invalidateQueries({ queryKey: SUGGESTIONS_QUERY_KEY });
    void queryClient.invalidateQueries({ queryKey: FILTER_RULES_QUERY_KEY });
  };
  const mineMutation = useMutation({
    mutationFn: mineRuleSuggestions,
    onSuccess: ({ mined }) => toast.success(mined ? `Found ${mined} suggestion${mined === 1 ? '' : 's'}` : 'No new suggestions'),
    onError: () => toast.error('Mining suggestions failed'),
    onSettled: refresh,
  });
  const acceptMutation = useMutation({
    mutationFn: ({ suggestion, overrides }: { suggestion: RuleSuggestion; overrides?: SuggestionOverrides }) => acceptRuleSuggestion(suggestion.id, overrides),
    onSuccess: ({ rule }) => toast.success(`Rule "${rule.name}" added; run the rules to apply it to existing tracks`),
    onError: (error) => toast.error(ruleErrorMessage(error, 'Could not add the rule')),
    onSettled: refresh,
  });
  const dismissMutation = useMutation({
    mutationFn: (suggestion: RuleSuggestion) => dismissRuleSuggestion(suggestion.id),
    onError: () => toast.error('Dismiss failed'),
    onSettled: refresh,
  });
  const busy = acceptMutation.isPending ? acceptMutation.variables?.suggestion : dismissMutation.isPending ? dismissMutation.variables : undefined;
  return {
    mine: () => mineMutation.mutate(),
    isMining: mineMutation.isPending,
    accept: (suggestion, overrides) => acceptMutation.mutate({ suggestion, overrides }),
    dismiss: (suggestion) => dismissMutation.mutate(suggestion),
    busyId: busy?.id ?? null,
  };
}

/** Rules proposed from what Kevin's own flags have in common. */
export function RuleSuggestionsPanel(): JSX.Element {
  const suggestionsQuery = useQuery({ queryKey: SUGGESTIONS_QUERY_KEY, queryFn: () => getRuleSuggestions() });
  const { mine, isMining, accept, dismiss, busyId } = useSuggestionMutations();
  const suggestions = suggestionsQuery.data ?? [];
  return (
    <section className="space-y-3" aria-label="Rule suggestions">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="text-lg font-semibold text-white">Suggestions</h3>
          <p className="text-sm text-white/50">Rules your own flags have in common. Nothing changes until you accept one.</p>
        </div>
        <button type="button" onClick={mine} disabled={isMining} className={SMALL_BUTTON}>
          {isMining ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
          Find suggestions
        </button>
      </div>
      {suggestionsQuery.isError && <p className="text-sm text-white/50" role="alert">Failed to load suggestions</p>}
      {!suggestionsQuery.isLoading && !suggestionsQuery.isError && suggestions.length === 0 && (
        <p className="text-sm text-white/40">No pending suggestions.</p>
      )}
      <div className="flex flex-col gap-2">
        {suggestions.map((suggestion) => (
          <SuggestionRow key={suggestion.id} suggestion={suggestion} isBusy={busyId === suggestion.id} onAccept={accept} onDismiss={dismiss} />
        ))}
      </div>
    </section>
  );
}

interface ClassificationRowProps {
  item: FeedClassification;
  isBusy: boolean;
  onPlay: (item: FeedClassification) => void;
  onResolve: (item: FeedClassification, confirm: boolean) => void;
}

export function ClassificationRow({ item, isBusy, onPlay, onResolve }: ClassificationRowProps): JSX.Element {
  const title = item.title ?? 'Untitled';
  return (
    <article aria-label={`${title} agent suggestion`} className="flex flex-wrap items-center gap-3 rounded border border-obsidian-border bg-obsidian-surface px-3 py-2 md:flex-nowrap">
      <button type="button" onClick={() => onPlay(item)} disabled={item.access === 'blocked'} className="min-w-0 flex-1 text-left disabled:opacity-40" aria-label={`Play ${title}`}>
        <p className="truncate text-sm text-white">{title}</p>
        <p className="truncate text-xs text-white/50">{item.uploader ?? 'Unknown artist'}{item.genre ? ` · ${item.genre}` : ''}</p>
      </button>
      <span className="shrink-0 font-sf-mono text-xs text-white/40">{formatFlagDuration(item.duration_ms)}</span>
      <span className="shrink-0 font-sf-mono text-xs text-white" title="Jev's confidence that this is a mix, set or show">{formatConfidence(item.mix_probability)}</span>
      <button type="button" disabled={isBusy} onClick={() => onResolve(item, true)} aria-label={`Filter ${title}`} className={`${SMALL_BUTTON} hover:border-obsidian-accent hover:text-obsidian-accent`}>
        Not for feed
      </button>
      <button type="button" disabled={isBusy} onClick={() => onResolve(item, false)} aria-label={`Keep ${title} in feed`} className={SMALL_BUTTON}>
        Real track
      </button>
    </article>
  );
}

function useClassifyMutations(): {
  classify: () => void;
  isClassifying: boolean;
  resolve: (item: FeedClassification, confirm: boolean) => void;
  busyId: number | null;
} {
  const queryClient = useQueryClient();
  const refresh = (): void => {
    void queryClient.invalidateQueries({ queryKey: CLASSIFICATIONS_QUERY_KEY });
    void queryClient.invalidateQueries({ queryKey: FEED_QUERY_PREFIX });
    invalidateFlagViews(queryClient);
  };
  const classifyMutation = useMutation({
    mutationFn: () => classifyAmbiguousTracks(),
    onSuccess: (result) => toast.success(describeClassifyResult(result)),
    onError: (error) => toast.error(ruleErrorMessage(error, 'Jev classification failed')),
    onSettled: refresh,
  });
  const resolveMutation = useMutation({
    mutationFn: ({ item, confirm }: { item: FeedClassification; confirm: boolean }) => resolveClassification(item.id, confirm),
    onError: () => toast.error('Could not save your answer'),
    onSettled: refresh,
  });
  return {
    classify: () => classifyMutation.mutate(),
    isClassifying: classifyMutation.isPending,
    resolve: (item, confirm) => resolveMutation.mutate({ item, confirm }),
    busyId: resolveMutation.isPending ? (resolveMutation.variables?.item.id ?? null) : null,
  };
}

interface UnreadableNoticeProps {
  count: number;
  isRetrying: boolean;
  onRetry: () => void;
}

/** Tracks Jev gave unreadable answers for; they're skipped until reset. */
export function UnreadableNotice({ count, isRetrying, onRetry }: UnreadableNoticeProps): JSX.Element | null {
  if (count === 0) return null;
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 rounded border border-obsidian-border px-3 py-2">
      <p className="text-sm text-white/50">
        {count} track{count === 1 ? '' : 's'} got unreadable answers and won't be checked again.
      </p>
      <button type="button" onClick={onRetry} disabled={isRetrying} className={SMALL_BUTTON}>
        {isRetrying ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RotateCcw className="h-3.5 w-3.5" />}
        Retry unreadable
      </button>
    </div>
  );
}

function useUnreadable(): UnreadableNoticeProps {
  const queryClient = useQueryClient();
  const countQuery = useQuery({ queryKey: UNREADABLE_QUERY_KEY, queryFn: getUnreadableCount });
  const retryMutation = useMutation({
    mutationFn: retryUnreadable,
    onSuccess: (reset) => toast.success(`${reset} track${reset === 1 ? '' : 's'} will be checked on the next run`),
    onError: () => toast.error('Could not reset unreadable tracks'),
    onSettled: () => void queryClient.invalidateQueries({ queryKey: UNREADABLE_QUERY_KEY }),
  });
  return { count: countQuery.data ?? 0, isRetrying: retryMutation.isPending, onRetry: () => retryMutation.mutate() };
}

/** Jev's mix / set / show calls between 50% and 85%: Kevin decides. */
export function AgentReviewPanel(): JSX.Element {
  const classificationsQuery = useQuery({ queryKey: CLASSIFICATIONS_QUERY_KEY, queryFn: () => getClassifications('pending') });
  const { classify, isClassifying, resolve, busyId } = useClassifyMutations();
  const unreadable = useUnreadable();
  const playRow = usePlayFeedRow();
  const items = classificationsQuery.data ?? [];
  const play = (item: FeedClassification): void => void playRow({ ...item, artist_name: item.uploader });
  return (
    <section className="space-y-3" aria-label="Agent review">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="text-lg font-semibold text-white">Agent</h3>
          <p className="text-sm text-white/50">
            Jev checks unreviewed 8-20 minute tracks no rule caught. At 85%+ it filters them; between 50% and 85% it asks you here.
          </p>
        </div>
        <button type="button" onClick={classify} disabled={isClassifying} className={SMALL_BUTTON}>
          {isClassifying ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Bot className="h-3.5 w-3.5" />}
          Check ambiguous tracks
        </button>
      </div>
      <UnreadableNotice {...unreadable} />
      {classificationsQuery.isError && <p className="text-sm text-white/50" role="alert">Failed to load agent suggestions</p>}
      {!classificationsQuery.isLoading && !classificationsQuery.isError && items.length === 0 && (
        <p className="text-sm text-white/40">Nothing waiting for review.</p>
      )}
      <div className="flex flex-col gap-2">
        {items.map((item) => (
          <ClassificationRow key={item.id} item={item} isBusy={busyId === item.id} onPlay={play} onResolve={resolve} />
        ))}
      </div>
    </section>
  );
}
