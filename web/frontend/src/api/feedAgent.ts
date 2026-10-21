// Re-export from shared package
export {
  classifyAmbiguousTracks, getClassifications, resolveClassification,
  mineRuleSuggestions, getRuleSuggestions, acceptRuleSuggestion,
  dismissRuleSuggestion, describeClassifyResult,
} from '@music-minion/shared';
export type {
  ClassificationStatus, FeedClassification, ClassifyResult, SuggestionStatus,
  RuleSuggestion, SuggestionOverrides,
} from '@music-minion/shared';
