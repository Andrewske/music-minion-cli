import { getDefaultApiClient } from './client';
import type { FilterRule, FilterRuleKind, FlagReason } from './feedFilters';

/**
 * Feed agent (#31): Jev classifies ambiguous tracks as mixes / shows, and
 * rule suggestions are mined from Kevin's flags. The agent only writes flags
 * and suggestions; rules exist only once a suggestion is accepted.
 */

export type ClassificationStatus = 'auto_flagged' | 'pending' | 'below_threshold' | 'confirmed' | 'dismissed';

export interface FeedClassification {
  id: number;
  soundcloud_id: string;
  model_id: string;
  /** Jev's probability that the track is a mix, set or show. */
  mix_probability: number;
  podcast_probability: number | null;
  status: ClassificationStatus;
  created_at: string;
  local_track_id: number | null;
  title: string | null;
  uploader: string | null;
  genre: string | null;
  tags: string[];
  duration_ms: number;
  artwork_url: string | null;
  permalink_url: string | null;
  access: string | null;
}

export interface ClassifyResult {
  candidates: number;
  classified: number;
  auto_flagged: number;
  pending: number;
  invalid: number;
  failed_batches: number;
}

export type SuggestionStatus = 'pending' | 'accepted' | 'dismissed';

export interface RuleSuggestion {
  id: number;
  signature: string;
  name: string;
  kind: FilterRuleKind;
  pattern: string | null;
  threshold: number | null;
  reason: FlagReason;
  /** Flags the rule would catch that no enabled rule already does. */
  support: number;
  /** Real tracks (rescued, dismissed, kept, not quite) it would also catch. */
  counter: number;
  evidence: string;
  status: SuggestionStatus;
  rule_id: number | null;
}

export interface SuggestionOverrides {
  name?: string;
  pattern?: string;
  threshold?: number;
  reason?: FlagReason;
}

export async function classifyAmbiguousTracks(maxTracks?: number): Promise<ClassifyResult> {
  return getDefaultApiClient().post<ClassifyResult>(
    '/feed-filters/classify',
    maxTracks === undefined ? undefined : { max_tracks: maxTracks }
  );
}

export async function getClassifications(status: ClassificationStatus = 'pending'): Promise<FeedClassification[]> {
  const response = await getDefaultApiClient().request<{ items: FeedClassification[] }>(
    `/feed-filters/classifications?status=${status}`
  );
  return response.items;
}

/** Confirm = Kevin agrees it's a mix / show and the track gets his own flag. */
export async function resolveClassification(id: number, confirm: boolean): Promise<FeedClassification> {
  return getDefaultApiClient().post<FeedClassification>(
    `/feed-filters/classifications/${id}/${confirm ? 'confirm' : 'dismiss'}`
  );
}

export async function mineRuleSuggestions(): Promise<{ mined: number; suggestions: RuleSuggestion[] }> {
  return getDefaultApiClient().post('/feed-filters/suggestions/mine');
}

export async function getRuleSuggestions(status: SuggestionStatus = 'pending'): Promise<RuleSuggestion[]> {
  const response = await getDefaultApiClient().request<{ suggestions: RuleSuggestion[] }>(
    `/feed-filters/suggestions?status=${status}`
  );
  return response.suggestions;
}

/** Creates a real rule; an invalid edited regex is rejected with the reason. */
export async function acceptRuleSuggestion(
  id: number,
  overrides?: SuggestionOverrides
): Promise<{ suggestion: RuleSuggestion; rule: FilterRule }> {
  return getDefaultApiClient().post(`/feed-filters/suggestions/${id}/accept`, overrides);
}

export async function dismissRuleSuggestion(id: number): Promise<RuleSuggestion> {
  return getDefaultApiClient().post<RuleSuggestion>(`/feed-filters/suggestions/${id}/dismiss`);
}

/** "Classified 12: 2 filtered, 3 to review" style toast text. */
export function describeClassifyResult(result: ClassifyResult): string {
  if (result.candidates === 0) return 'No ambiguous tracks to check';
  const parts = [`${result.auto_flagged} filtered`, `${result.pending} to review`];
  const failed = result.failed_batches > 0 ? ` (${result.failed_batches} batch${result.failed_batches === 1 ? '' : 'es'} failed)` : '';
  const invalid = result.invalid > 0 ? ` (${result.invalid} unreadable answer${result.invalid === 1 ? '' : 's'})` : '';
  return `Checked ${result.classified} of ${result.candidates}: ${parts.join(', ')}${failed}${invalid}`;
}
