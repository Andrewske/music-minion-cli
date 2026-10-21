import { getDefaultApiClient } from './client';

/** Why a track is not for the feed. Not a verdict: it never trains taste. */
export type FlagReason = 'live_mix' | 'podcast' | 'other';
export type FlagSource = 'user' | 'rule' | 'agent';
/** 'filtered' = everything a rule or the agent caught. */
export type FlaggedSourceFilter = 'filtered' | FlagSource;
export type FilterRuleKind = 'duration_min' | 'title_regex' | 'tag_match';

export const FLAG_REASONS: readonly FlagReason[] = ['live_mix', 'podcast', 'other'];
export const FLAG_REASON_LABELS: Record<FlagReason, string> = {
  live_mix: 'Live mix / set',
  podcast: 'Podcast / radio show',
  other: 'Other',
};
export const FILTER_RULE_KINDS: readonly FilterRuleKind[] = ['duration_min', 'title_regex', 'tag_match'];
export const FILTER_RULE_KIND_LABELS: Record<FilterRuleKind, string> = {
  duration_min: 'Longer than (min)',
  title_regex: 'Title matches regex',
  tag_match: 'Genre/tag is one of',
};

export interface FeedFlag {
  id: number;
  soundcloud_id: string;
  reason: FlagReason;
  source: FlagSource;
  rule_id: number | null;
  created_at: string;
  rescued_at: string | null;
}

export interface FlaggedItem {
  flag_id: number;
  soundcloud_id: string;
  reason: FlagReason;
  source: FlagSource;
  rule_id: number | null;
  rule_name: string | null;
  created_at: string;
  local_track_id: number | null;
  title: string | null;
  artist_name: string | null;
  artwork_url: string | null;
  permalink_url: string | null;
  duration_ms: number;
  access: string | null;
  note: string | null;
}

export interface FlaggedPage {
  items: FlaggedItem[];
  next_cursor: number | null;
}

export interface FilterRule {
  id: number;
  name: string;
  kind: FilterRuleKind;
  pattern: string | null;
  /** Minutes, for duration_min rules. */
  threshold: number | null;
  reason: FlagReason;
  enabled: boolean;
  seed_key: string | null;
  created_at: string;
  updated_at: string;
  hits: number;
  rescues: number;
  /** 1 - rescues / hits; null until the rule has caught something. */
  precision: number | null;
}

export interface FilterRuleInput {
  name: string;
  kind: FilterRuleKind;
  reason: FlagReason;
  pattern?: string | null;
  threshold?: number | null;
  enabled?: boolean;
}

export interface UnflagResponse {
  soundcloud_id: string;
  source: FlagSource;
  /** True when a user flag was undone; false when a rule flag was rescued. */
  removed: boolean;
  rescued_at: string | null;
}

export interface GetFlaggedParams {
  source?: FlaggedSourceFilter;
  ruleId?: number;
  cursor?: number;
  limit?: number;
}

export const FLAGGED_PAGE_SIZE = 50;

export async function flagFeedItem(
  soundcloudId: string,
  reason: FlagReason,
  note?: string
): Promise<{ soundcloud_id: string; flag: FeedFlag }> {
  const body = note?.trim() ? { reason, note } : { reason };
  return getDefaultApiClient().post(`/feed/${encodeURIComponent(soundcloudId)}/flag`, body);
}

/** Undo a user flag, or rescue a rule/agent flag; either way it returns to the feed. */
export async function unflagFeedItem(soundcloudId: string): Promise<UnflagResponse> {
  return getDefaultApiClient().request<UnflagResponse>(
    `/feed/${encodeURIComponent(soundcloudId)}/flag`,
    { method: 'DELETE' }
  );
}

export async function getFlaggedTracks(params: GetFlaggedParams = {}): Promise<FlaggedPage> {
  const query = new URLSearchParams();
  query.set('limit', String(params.limit ?? FLAGGED_PAGE_SIZE));
  query.set('source', params.source ?? 'filtered');
  if (params.ruleId !== undefined) query.set('rule_id', String(params.ruleId));
  if (params.cursor !== undefined) query.set('cursor', String(params.cursor));
  return getDefaultApiClient().request<FlaggedPage>(`/feed-filters/tracks?${query.toString()}`);
}

export async function getFilterRules(): Promise<FilterRule[]> {
  const response = await getDefaultApiClient().request<{ rules: FilterRule[] }>('/feed-filters/rules');
  return response.rules;
}

/** Invalid regexes are rejected server-side; the ApiError message says why. */
export async function createFilterRule(input: FilterRuleInput): Promise<FilterRule> {
  return getDefaultApiClient().post<FilterRule>('/feed-filters/rules', input);
}

export async function updateFilterRule(
  ruleId: number,
  changes: Partial<FilterRuleInput>
): Promise<FilterRule> {
  return getDefaultApiClient().request<FilterRule>(`/feed-filters/rules/${ruleId}`, {
    method: 'PATCH',
    body: JSON.stringify(changes),
  });
}

export async function deleteFilterRule(ruleId: number): Promise<{ deleted: boolean; id: number }> {
  return getDefaultApiClient().request(`/feed-filters/rules/${ruleId}`, { method: 'DELETE' });
}

/** Apply enabled rules to every unreviewed, never-flagged track. */
export async function runFilterRules(): Promise<{ flagged: number }> {
  return getDefaultApiClient().post<{ flagged: number }>('/feed-filters/run');
}

/** "92%" or "-" before the rule has caught anything. */
export function formatPrecision(precision: number | null): string {
  return precision === null ? '-' : `${Math.round(precision * 100)}%`;
}

/** The editable value of a rule as shown in one text field. */
export function ruleCriterion(rule: Pick<FilterRule, 'kind' | 'pattern' | 'threshold'>): string {
  return rule.kind === 'duration_min' ? String(rule.threshold ?? '') : (rule.pattern ?? '');
}

/** Turn an edited criterion back into the PATCH fields for that rule kind. */
export function criterionChanges(
  kind: FilterRuleKind,
  value: string
): Pick<FilterRuleInput, 'pattern' | 'threshold'> {
  return kind === 'duration_min' ? { threshold: Number(value) } : { pattern: value };
}
