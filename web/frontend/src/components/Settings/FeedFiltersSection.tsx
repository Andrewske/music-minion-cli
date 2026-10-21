import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Loader2, Play, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import {
  FILTER_RULE_KINDS,
  FILTER_RULE_KIND_LABELS,
  FLAG_REASONS,
  FLAG_REASON_LABELS,
  createFilterRule,
  criterionChanges,
  deleteFilterRule,
  formatPrecision,
  getFilterRules,
  ruleCriterion,
  runFilterRules,
  updateFilterRule,
  type FilterRule,
  type FilterRuleInput,
  type FilterRuleKind,
  type FlagReason,
} from '../../api/feedFilters';
import { usePlayFeedRow } from '../../hooks/usePlayFeedRow';
import { usePlayerStore } from '../../stores/playerStore';
import { FlaggedList } from '../feed/FlaggedList';
import { ruleErrorMessage } from '../feed/flagged';
import { FILTER_RULES_QUERY_KEY, FLAGGED_QUERY_KEY } from '../feed/reviewed';
import { Switch } from '../ui/switch';

const FIELD = 'rounded border border-obsidian-border bg-black/30 px-2 py-1.5 text-sm text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-obsidian-accent';

function criterionPlaceholder(kind: FilterRuleKind): string {
  if (kind === 'duration_min') return 'Minutes, e.g. 15';
  return kind === 'title_regex' ? 'Regex, e.g. live at|b2b' : 'Tags, e.g. podcast, radio';
}

function ReasonSelect({ value, onChange, label }: { value: FlagReason; onChange: (reason: FlagReason) => void; label: string }): JSX.Element {
  return (
    <select aria-label={label} value={value} onChange={(event) => onChange(event.target.value as FlagReason)} className={FIELD}>
      {FLAG_REASONS.map((reason) => <option key={reason} value={reason}>{FLAG_REASON_LABELS[reason]}</option>)}
    </select>
  );
}

function useRuleMutations(): {
  update: (rule: FilterRule, changes: Partial<FilterRuleInput>) => void;
  remove: (rule: FilterRule) => void;
} {
  const queryClient = useQueryClient();
  const refresh = (): void => {
    void queryClient.invalidateQueries({ queryKey: FILTER_RULES_QUERY_KEY });
    void queryClient.invalidateQueries({ queryKey: FLAGGED_QUERY_KEY });
    void queryClient.invalidateQueries({ queryKey: ['feed'] });
    void queryClient.invalidateQueries({ queryKey: ['artists'] });
  };
  const updateMutation = useMutation({
    mutationFn: ({ rule, changes }: { rule: FilterRule; changes: Partial<FilterRuleInput> }) => updateFilterRule(rule.id, changes),
    onError: (error) => toast.error(ruleErrorMessage(error, 'Rule update failed')),
    onSettled: refresh,
  });
  const deleteMutation = useMutation({
    mutationFn: (rule: FilterRule) => deleteFilterRule(rule.id),
    onSuccess: () => toast.success('Rule deleted; its tracks are back in the feed'),
    onError: () => toast.error('Rule delete failed'),
    onSettled: refresh,
  });
  return {
    update: (rule, changes) => updateMutation.mutate({ rule, changes }),
    remove: (rule) => deleteMutation.mutate(rule),
  };
}

interface RuleRowProps {
  rule: FilterRule;
  onUpdate: (rule: FilterRule, changes: Partial<FilterRuleInput>) => void;
  onDelete: (rule: FilterRule) => void;
}

export function RuleRow({ rule, onUpdate, onDelete }: RuleRowProps): JSX.Element {
  const saved = ruleCriterion(rule);
  const [draft, setDraft] = useState(saved);
  const save = (): void => {
    if (draft.trim() !== saved) onUpdate(rule, criterionChanges(rule.kind, draft.trim()));
  };
  return (
    <tr className="border-t border-obsidian-border align-middle">
      <td className="py-2 pr-2">
        <Switch checked={rule.enabled} onCheckedChange={(enabled) => onUpdate(rule, { enabled })} aria-label={`Enable ${rule.name}`} />
      </td>
      <td className="py-2 pr-2">
        <p className="text-sm text-white">{rule.name}</p>
        <p className="text-[11px] text-white/40">{FILTER_RULE_KIND_LABELS[rule.kind]}</p>
      </td>
      <td className="py-2 pr-2">
        <input
          aria-label={`${rule.name} criterion`}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onBlur={save}
          onKeyDown={(event) => event.key === 'Enter' && save()}
          className={`${FIELD} w-full min-w-40 font-sf-mono text-xs`}
        />
      </td>
      <td className="py-2 pr-2">
        <ReasonSelect label={`${rule.name} reason`} value={rule.reason} onChange={(reason) => onUpdate(rule, { reason })} />
      </td>
      <td className="py-2 pr-2 text-right font-sf-mono text-xs text-white/70">{rule.hits}</td>
      <td className="py-2 pr-2 text-right font-sf-mono text-xs text-white/70">{rule.rescues}</td>
      <td className="py-2 pr-2 text-right font-sf-mono text-xs text-white">{formatPrecision(rule.precision)}</td>
      <td className="py-2 text-right">
        <button type="button" onClick={() => onDelete(rule)} aria-label={`Delete ${rule.name}`} className="rounded p-2 text-white/40 hover:bg-white/10 hover:text-red-400">
          <Trash2 className="h-4 w-4" />
        </button>
      </td>
    </tr>
  );
}

const EMPTY_RULE = { name: '', kind: 'title_regex' as FilterRuleKind, criterion: '', reason: 'live_mix' as FlagReason };

function NewRuleForm(): JSX.Element {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState(EMPTY_RULE);
  const createMutation = useMutation({
    mutationFn: () =>
      createFilterRule({ name: draft.name, kind: draft.kind, reason: draft.reason, ...criterionChanges(draft.kind, draft.criterion.trim()) }),
    onSuccess: () => {
      setDraft(EMPTY_RULE);
      toast.success('Rule added; it applies to new tracks, or run it on existing ones');
    },
    onError: (error) => toast.error(ruleErrorMessage(error, 'Rule could not be added')),
    onSettled: () => queryClient.invalidateQueries({ queryKey: FILTER_RULES_QUERY_KEY }),
  });
  return (
    <form
      aria-label="Add filter rule"
      onSubmit={(event) => { event.preventDefault(); createMutation.mutate(); }}
      className="flex flex-wrap items-center gap-2"
    >
      <input aria-label="New rule name" placeholder="Rule name" value={draft.name} onChange={(event) => setDraft({ ...draft, name: event.target.value })} className={`${FIELD} w-40`} />
      <select aria-label="New rule kind" value={draft.kind} onChange={(event) => setDraft({ ...draft, kind: event.target.value as FilterRuleKind })} className={FIELD}>
        {FILTER_RULE_KINDS.map((kind) => <option key={kind} value={kind}>{FILTER_RULE_KIND_LABELS[kind]}</option>)}
      </select>
      <input aria-label="New rule criterion" placeholder={criterionPlaceholder(draft.kind)} value={draft.criterion} onChange={(event) => setDraft({ ...draft, criterion: event.target.value })} className={`${FIELD} min-w-48 flex-1 font-sf-mono text-xs`} />
      <ReasonSelect label="New rule reason" value={draft.reason} onChange={(reason) => setDraft({ ...draft, reason })} />
      <button type="submit" disabled={createMutation.isPending} className="rounded-lg bg-obsidian-accent/20 px-4 py-2 text-sm font-medium text-obsidian-accent hover:bg-obsidian-accent/30 disabled:opacity-50">
        Add rule
      </button>
    </form>
  );
}

function RulesTable({ rules }: { rules: FilterRule[] }): JSX.Element {
  const { update, remove } = useRuleMutations();
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left">
        <thead className="text-[11px] uppercase tracking-wide text-white/40">
          <tr>
            <th className="pb-2 pr-2 font-normal">On</th>
            <th className="pb-2 pr-2 font-normal">Rule</th>
            <th className="pb-2 pr-2 font-normal">Pattern / threshold</th>
            <th className="pb-2 pr-2 font-normal">Reason</th>
            <th className="pb-2 pr-2 text-right font-normal">Hits</th>
            <th className="pb-2 pr-2 text-right font-normal">Rescues</th>
            <th className="pb-2 pr-2 text-right font-normal" title="1 - rescues / hits">Precision</th>
            <th className="pb-2" aria-label="Actions" />
          </tr>
        </thead>
        <tbody>
          {/* Keyed on the saved criterion so a rejected edit resets the field. */}
          {rules.map((rule) => <RuleRow key={`${rule.id}:${ruleCriterion(rule)}`} rule={rule} onUpdate={update} onDelete={remove} />)}
        </tbody>
      </table>
    </div>
  );
}

function RunRulesButton(): JSX.Element {
  const queryClient = useQueryClient();
  const runMutation = useMutation({
    mutationFn: runFilterRules,
    onSuccess: ({ flagged }) => toast.success(`Filtered ${flagged} existing track${flagged === 1 ? '' : 's'}`),
    onError: () => toast.error('Running the rules failed'),
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: FILTER_RULES_QUERY_KEY });
      void queryClient.invalidateQueries({ queryKey: FLAGGED_QUERY_KEY });
      void queryClient.invalidateQueries({ queryKey: ['feed'] });
    },
  });
  return (
    <button type="button" onClick={() => runMutation.mutate()} disabled={runMutation.isPending} className="flex items-center gap-2 rounded border border-obsidian-border px-3 py-1.5 text-xs text-white/70 hover:text-white disabled:opacity-50">
      {runMutation.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
      Run on unreviewed tracks
    </button>
  );
}

function FilteredTracks({ rules }: { rules: FilterRule[] }): JSX.Element {
  const [ruleId, setRuleId] = useState<number | undefined>(undefined);
  const currentTrackId = usePlayerStore((state) => state.currentTrack?.id ?? null);
  const playRow = usePlayFeedRow();
  return (
    <section className="space-y-3" aria-label="Filtered tracks">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-lg font-semibold text-white">Filtered tracks</h3>
        <select aria-label="Filter by rule" value={ruleId ?? ''} onChange={(event) => setRuleId(event.target.value ? Number(event.target.value) : undefined)} className={FIELD}>
          <option value="">All rules</option>
          {rules.map((rule) => <option key={rule.id} value={rule.id}>{rule.name}</option>)}
        </select>
      </div>
      <FlaggedList source="filtered" ruleId={ruleId} currentTrackId={currentTrackId} emptyText="No tracks filtered yet." onPlay={(item) => void playRow(item)} />
    </section>
  );
}

/** Settings: rules that hide live mixes, sets and shows, and what they caught. */
export function FeedFiltersSection(): JSX.Element {
  const rulesQuery = useQuery({ queryKey: FILTER_RULES_QUERY_KEY, queryFn: getFilterRules });
  const rules = rulesQuery.data ?? [];
  return (
    <div className="space-y-8">
      <section className="space-y-3" aria-label="Filter rules">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h3 className="text-lg font-semibold text-white">Rules</h3>
            <p className="text-sm text-white/50">New tracks a rule catches skip the feed. Rescues lower that rule's precision.</p>
          </div>
          <RunRulesButton />
        </div>
        {rulesQuery.isLoading ? (
          <div className="flex justify-center py-6 text-white/40" role="status" aria-label="Loading rules"><Loader2 className="h-5 w-5 animate-spin" /></div>
        ) : rulesQuery.isError ? (
          <p className="text-sm text-white/50" role="alert">Failed to load rules</p>
        ) : (
          <RulesTable rules={rules} />
        )}
        <NewRuleForm />
      </section>
      <FilteredTracks rules={rules} />
    </div>
  );
}
