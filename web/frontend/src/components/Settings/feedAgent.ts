import type { RuleSuggestion, SuggestionOverrides } from '../../api/feedAgent';
import { criterionChanges, ruleCriterion, type FlagReason } from '../../api/feedFilters';

export const SUGGESTIONS_QUERY_KEY = ['feed-filters', 'suggestions'] as const;
export const CLASSIFICATIONS_QUERY_KEY = ['feed-filters', 'classifications'] as const;
export const UNREADABLE_QUERY_KEY = ['feed-filters', 'classifications', 'unreadable'] as const;

/** Only the fields Kevin changed are sent; the server re-validates the rule. */
export function suggestionOverrides(suggestion: RuleSuggestion, criterion: string, reason: FlagReason): SuggestionOverrides | undefined {
  const overrides: SuggestionOverrides = {};
  if (criterion.trim() !== ruleCriterion(suggestion)) {
    const changes = criterionChanges(suggestion.kind, criterion.trim());
    if (changes.pattern != null) overrides.pattern = changes.pattern;
    if (changes.threshold != null) overrides.threshold = changes.threshold;
  }
  if (reason !== suggestion.reason) overrides.reason = reason;
  return Object.keys(overrides).length > 0 ? overrides : undefined;
}
