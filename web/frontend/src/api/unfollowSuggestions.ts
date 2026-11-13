// Re-export from shared package
export {
  getUnfollowSuggestions, keepFollowing, unfollowSuggested, unfollowBatch, UNFOLLOW_BATCH_SIZE,
} from '@music-minion/shared';
export type {
  UnfollowCandidate, UnfollowSection, UnfollowSuggestionsResponse, UnfollowBatchResult,
  UnfollowBatchResponse, UnfollowAccountResponse,
} from '@music-minion/shared';
